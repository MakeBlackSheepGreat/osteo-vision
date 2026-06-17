import torch
import torch.nn as nn
import torch.nn.functional as F
from model.lib.pvtv2 import pvt_v2_b2
import os
import torch
import torch.nn as nn
import torch.nn.functional as F
from mmcv.cnn import ConvModule
from torch.nn import Conv2d, UpsamplingBilinear2d
import warnings
import torch
from mmcv.cnn import constant_init, kaiming_init
from torch import nn
from torchvision.transforms.functional import normalize
warnings.filterwarnings('ignore')
       
       
class BasicConv2d(nn.Module):
    def __init__(self, in_planes, out_planes, kernel_size, stride=1, padding=0, dilation=1):
        super(BasicConv2d, self).__init__()

        self.conv = nn.Conv2d(in_planes, out_planes,
                              kernel_size=kernel_size, stride=stride,
                              padding=padding, dilation=dilation, bias=False)
        self.bn = nn.BatchNorm2d(out_planes)
        self.relu = nn.ReLU(inplace=True)

    def forward(self, x):
        x = self.conv(x)
        x = self.bn(x)
        x = self.relu(x)
        return x
        
class Block(nn.Sequential):
    def __init__(self, input_num, num1, num2, dilation_rate, drop_out, bn_start=True, norm_layer=nn.BatchNorm2d):
        super(Block, self).__init__()
        if bn_start:
            self.add_module('norm1', norm_layer(input_num)),

        self.add_module('relu1', nn.ReLU(inplace=True)),
        self.add_module('conv1', nn.Conv2d(in_channels=input_num, out_channels=num1, kernel_size=1)),

        self.add_module('norm2', norm_layer(num1)),
        self.add_module('relu2', nn.ReLU(inplace=True)),
        self.add_module('conv2', nn.Conv2d(in_channels=num1, out_channels=num2, kernel_size=3,
                                            dilation=dilation_rate, padding=dilation_rate)),
        self.drop_rate = drop_out

    def forward(self, _input):
        feature = super(Block, self).forward(_input)
        if self.drop_rate > 0:
            feature = F.dropout2d(feature, p=self.drop_rate, training=self.training)
        return feature


def Upsample(x, size, align_corners = False):
    """
    Wrapper Around the Upsample Call
    """
    return nn.functional.interpolate(x, size=size, mode='bilinear', align_corners=align_corners)

    
def last_zero_init(m):
    if isinstance(m, nn.Sequential):
        constant_init(m[-1], val=0)
    else:
        constant_init(m, val=0)


class ContextBlock(nn.Module):

    def __init__(self,
                 inplanes,
                 ratio,
                 pooling_type='att',
                 fusion_types=('channel_mul', )):
        super(ContextBlock, self).__init__()
        assert pooling_type in ['avg', 'att']
        assert isinstance(fusion_types, (list, tuple))
        valid_fusion_types = ['channel_add', 'channel_mul']
        assert all([f in valid_fusion_types for f in fusion_types])
        assert len(fusion_types) > 0, 'at least one fusion should be used'
        self.inplanes = inplanes
        self.ratio = ratio
        self.planes = int(inplanes * ratio)
        self.pooling_type = pooling_type
        self.fusion_types = fusion_types
        if pooling_type == 'att':
            self.conv_mask = nn.Conv2d(inplanes, 1, kernel_size=1)
            self.softmax = nn.Softmax(dim=2)
        else:
            self.avg_pool = nn.AdaptiveAvgPool2d(1)
        if 'channel_add' in fusion_types:
            self.channel_add_conv = nn.Sequential(
                nn.Conv2d(self.inplanes, self.planes, kernel_size=1),
                nn.LayerNorm([self.planes, 1, 1]),
                nn.ReLU(inplace=True),  # yapf: disable
                nn.Conv2d(self.planes, self.inplanes, kernel_size=1))
        else:
            self.channel_add_conv = None
        if 'channel_mul' in fusion_types:
            self.channel_mul_conv = nn.Sequential(
                nn.Conv2d(self.inplanes, self.planes, kernel_size=1),
                nn.LayerNorm([self.planes, 1, 1]),
                nn.ReLU(inplace=True),  # yapf: disable
                nn.Conv2d(self.planes, self.inplanes, kernel_size=1))
        else:
            self.channel_mul_conv = None
        self.reset_parameters()

    def reset_parameters(self):
        if self.pooling_type == 'att':
            kaiming_init(self.conv_mask, mode='fan_in')
            self.conv_mask.inited = True

        if self.channel_add_conv is not None:
            last_zero_init(self.channel_add_conv)
        if self.channel_mul_conv is not None:
            last_zero_init(self.channel_mul_conv)

    def spatial_pool(self, x):
        batch, channel, height, width = x.size()
        if self.pooling_type == 'att':
            input_x = x
            # [N, C, H * W]
            input_x = input_x.view(batch, channel, height * width)
            # [N, 1, C, H * W]
            input_x = input_x.unsqueeze(1)
            # [N, 1, H, W]
            context_mask = self.conv_mask(x)
            # [N, 1, H * W]
            context_mask = context_mask.view(batch, 1, height * width)
            # [N, 1, H * W]
            context_mask = self.softmax(context_mask)
            # [N, 1, H * W, 1]
            context_mask = context_mask.unsqueeze(-1)
            # [N, 1, C, 1]
            context = torch.matmul(input_x, context_mask)
            # [N, C, 1, 1]
            context = context.view(batch, channel, 1, 1)
        else:
            # [N, C, 1, 1]
            context = self.avg_pool(x)

        return context

    def forward(self, x):
        # [N, C, 1, 1]
        context = self.spatial_pool(x)

        out = x
        if self.channel_mul_conv is not None:
            # [N, C, 1, 1]
            channel_mul_term = torch.sigmoid(self.channel_mul_conv(context))
            out = out + out * channel_mul_term
        if self.channel_add_conv is not None:
            # [N, C, 1, 1]
            channel_add_term = self.channel_add_conv(context)
            out = out + channel_add_term

        return out



class ChannelAttention(nn.Module):
    def __init__(self, in_planes, ratio=16):
        super(ChannelAttention, self).__init__()
        self.avg_pool = nn.AdaptiveAvgPool2d(1)
        self.max_pool = nn.AdaptiveMaxPool2d(1)

        self.fc1   = nn.Conv2d(in_planes, in_planes // 16, 1, bias=False)
        self.relu1 = nn.ReLU()
        self.fc2   = nn.Conv2d(in_planes // 16, in_planes, 1, bias=False)

        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        avg_out = self.fc2(self.relu1(self.fc1(self.avg_pool(x))))
        max_out = self.fc2(self.relu1(self.fc1(self.max_pool(x))))
        out = avg_out + max_out
        return self.sigmoid(out)


class SpatialAttention(nn.Module):
    def __init__(self, kernel_size=7):
        super(SpatialAttention, self).__init__()

        assert kernel_size in (3, 7), 'kernel size must be 3 or 7'
        padding = 3 if kernel_size == 7 else 1

        self.conv1 = nn.Conv2d(2, 1, kernel_size, padding=padding, bias=False)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        avg_out = torch.mean(x, dim=1, keepdim=True)
        max_out, _ = torch.max(x, dim=1, keepdim=True)
        x = torch.cat([avg_out, max_out], dim=1)
        x = self.conv1(x)
        return self.sigmoid(x)


class ConvBranch(nn.Module):
    def __init__(self, in_features, hidden_features = None, out_features = None):
        super().__init__()
        hidden_features = hidden_features or in_features
        out_features = out_features or in_features
        self.conv1 = nn.Sequential(
            nn.Conv2d(in_features, hidden_features, 1, bias=False),
            nn.BatchNorm2d(hidden_features),
            nn.ReLU(inplace=True)
        )
        self.conv2 = nn.Sequential(
            nn.Conv2d(hidden_features, hidden_features, 3, padding=1, groups=hidden_features, bias=False),
            nn.BatchNorm2d(hidden_features),
            nn.ReLU(inplace=True)
        )
        self.conv3 = nn.Sequential(
            nn.Conv2d(hidden_features, hidden_features, 1, bias=False),
            nn.BatchNorm2d(hidden_features),
            nn.ReLU(inplace=True)
        )
        self.conv4 = nn.Sequential(
            nn.Conv2d(hidden_features, hidden_features, 3, padding=1, groups=hidden_features, bias=False),
            nn.BatchNorm2d(hidden_features),
            nn.ReLU(inplace=True)
        )
        self.conv5 = nn.Sequential(
            nn.Conv2d(hidden_features, hidden_features, 1, bias=False),
            nn.BatchNorm2d(hidden_features),
            nn.SiLU(inplace=True)
        )
        self.conv6 = nn.Sequential(
            nn.Conv2d(hidden_features, hidden_features, 3, padding=1, groups=hidden_features, bias=False),
            nn.BatchNorm2d(hidden_features),
            nn.ReLU(inplace=True)
        )
        self.conv7 = nn.Sequential(
            nn.Conv2d(hidden_features, out_features, 1, bias=False),
            nn.ReLU(inplace=True)
        )
        self.ca = ChannelAttention(64)
        self.sa = SpatialAttention()
        self.sigmoid_spatial = nn.Sigmoid()
    
    def forward(self, x):
        res1 = x
        res2 = x
        x = self.conv1(x)        
        x = x + self.conv2(x)
        x = self.conv3(x)
        x = x + self.conv4(x)
        x = self.conv5(x)
        x = x + self.conv6(x)
        x = self.conv7(x) #[64,32,8,8]
        x_mask = self.sigmoid_spatial(x)
        res1 = res1 * x_mask
        return res2 + res1

              
class GLSA(nn.Module):

    def __init__(self, input_dim=512, embed_dim=32, k_s=3):
        super().__init__()
                      
        self.conv1_1 = BasicConv2d(embed_dim*2,embed_dim, 1)
        self.conv1_1_1 = BasicConv2d(input_dim//2,embed_dim,1)
        self.local_11conv = nn.Conv2d(input_dim//2,embed_dim,1)
        self.global_11conv = nn.Conv2d(input_dim//2,embed_dim,1)
        self.GlobelBlock = ContextBlock(inplanes= embed_dim, ratio=2)
        self.local = ConvBranch(in_features = embed_dim, hidden_features = embed_dim, out_features = embed_dim)

    def forward(self, x):
        b, c, h, w = x.size()
        x_0, x_1 = x.chunk(2,dim = 1)  
        
    # local block 
        local = self.local(self.local_11conv(x_0))
        
    # Globel block    
        Globel = self.GlobelBlock(self.global_11conv(x_1))

    # concat Globel + local
        x = torch.cat([local,Globel], dim=1)
        x = self.conv1_1(x)

        return x    



# ---------------------- Laplacian Pyramid ----------------------
def gauss_kernel(channels=3, device='cuda'):
    kernel = torch.tensor([[1., 4., 6., 4., 1.],
                           [4., 16., 24., 16., 4.],
                           [6., 24., 36., 24., 6.],
                           [4., 16., 24., 16., 4.],
                           [1., 4., 6., 4., 1.]])
    kernel /= 256.
    kernel = kernel.repeat(channels, 1, 1, 1).to(device)
    return kernel

def conv_gauss(img, kernel):
    img = F.pad(img, (2, 2, 2, 2), mode='reflect')
    return F.conv2d(img, kernel, groups=img.shape[1])

def downsample(x):
    return x[:, :, ::2, ::2]

def upsample(x, channels):
    B, C, H, W = x.shape
    cc = torch.cat([x, torch.zeros_like(x)], dim=3)  # [B, C, H, 2W]
    cc = cc.view(B, C, H * 2, W)                     # [B, C, 2H, W]
    cc = cc.permute(0, 1, 3, 2)                      # [B, C, W, 2H]
    cc = torch.cat([cc, torch.zeros_like(cc)], dim=3)  # [B, C, W, 4H]
    cc = cc.view(B, C, W * 2, H * 2)
    x_up = cc.permute(0, 1, 3, 2)  # [B, C, H*2, W*2]
    return conv_gauss(x_up, 4 * gauss_kernel(channels, device=x.device))

def make_laplace(img, channels):
    filtered = conv_gauss(img, gauss_kernel(channels, device=img.device))
    down = downsample(filtered)
    up = upsample(down, channels)
    if up.shape[2:] != img.shape[2:]:
        up = F.interpolate(up, size=img.shape[2:], mode='bilinear', align_corners=False)
    return img - up

# ---------------------- SBA Module ----------------------
class SBA(nn.Module):
    def __init__(self, input_dim=32):
        super(SBA, self).__init__()

        self.d_in1 = BasicConv2d(input_dim, input_dim, 1)
        self.d_in2 = BasicConv2d(input_dim, input_dim, 1)

        self.conv = nn.Sequential(
            BasicConv2d(input_dim * 2, input_dim, 3, 1, 1),
            nn.Conv2d(input_dim, 1, kernel_size=1, bias=False)
        )

        self.fc1 = nn.Conv2d(input_dim, input_dim, kernel_size=1, bias=False)
        self.fc2 = nn.Conv2d(input_dim, input_dim, kernel_size=1, bias=False)

        self.sigmoid = nn.Sigmoid()

    def forward(self, H_feature, L_feature):

        L_lap = make_laplace(L_feature, channels=L_feature.shape[1])
        H_lap = make_laplace(H_feature, channels=H_feature.shape[1])

        L_proj = self.fc1(L_feature)
        H_proj = self.fc2(H_feature)

        g_L = self.sigmoid(L_proj)
        g_H = self.sigmoid(H_proj)

        L_mod = self.d_in1(L_proj)
        H_mod = self.d_in2(H_proj)
        L_mod_0 =  L_mod

        H_mod_up = F.interpolate(g_H * H_mod, size=L_feature.shape[2:], mode='bilinear', align_corners=False)
        L_mod = L_mod + L_mod * g_L + (1 - g_L) * H_mod_up

        L_lap = L_lap*g_L  
        H_lap = H_lap*g_H
        H_lap_up = F.interpolate(H_lap, size=L_feature.shape[2:], mode='bilinear', align_corners=False)
        H_mod = H_mod + H_mod * g_H + (1 - g_H) * F.interpolate(g_L * L_mod_0, size=H_feature.shape[2:], mode='bilinear', align_corners=False)
        H_mod = F.interpolate(H_mod, size=L_feature.shape[2:], mode='bilinear', align_corners=False)

        L_mod = L_mod + L_lap
        H_mod = H_mod + H_lap_up




        out = self.conv(torch.cat([H_mod, L_mod], dim=1))
        return out  # shape: [B, 1, 64, 64]



class ConvBNR(nn.Module):
    def __init__(self, in_c, out_c, kernel=3, stride=1, padding=1):
        super().__init__()
        self.conv = nn.Sequential(
                nn.Conv2d(in_c, out_c, kernel, stride, padding, bias=False),
                nn.BatchNorm2d(out_c),
                nn.ReLU(inplace=True)
                )
    def forward(self, x):
        return self.conv(x)

class EnhancedMultiScaleRefiner(nn.Module):
    def __init__(self, channels):
        super().__init__()
        self.down2 = nn.AvgPool2d(2)
        self.down4 = nn.AvgPool2d(4)
        
        self.conv_full = ConvBNR(channels, channels, 3)
        self.conv_half = ConvBNR(channels, channels, 3)
        self.conv_quarter = ConvBNR(channels, channels, 3)
        
        self.up2 = nn.Upsample(scale_factor=2, mode='bilinear', align_corners=True)
        self.up4 = nn.Upsample(scale_factor=4, mode='bilinear', align_corners=True)

        self.att = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Conv2d(channels, max(4, channels//8), 1),  # 确保最小通道数
            nn.ReLU(),
            nn.Conv2d(max(4, channels//8), channels, 1),
            nn.Sigmoid()
        )
    
    def forward(self, edge_map):
        full_res = self.conv_full(edge_map)
        
        # 1/2分辨率处理（中等结构）
        half_res = self.down2(edge_map)
        half_res = self.conv_half(half_res)
        half_res = self.up2(half_res)
        
        # 1/4分辨率处理（全局结构）
        quarter_res = self.down4(edge_map)
        quarter_res = self.conv_quarter(quarter_res)
        quarter_res = self.up4(quarter_res)
        
        # 自适应融合
        fused = full_res + half_res + quarter_res
        att = self.att(fused)
        return edge_map + fused * att
