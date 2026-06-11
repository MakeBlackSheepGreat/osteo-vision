from model.CRA import CrossAttentionBlock
from model.Encoder_pvt import Encoder
from model.Fusion import Up
from model.Transformer import Transformer
from model.lib.DuAT import *
from model.bgnet import *
import torch
import torch.nn as nn
import torch.nn.functional as F


class Net(nn.Module):
    def __init__(self, opt,dim=32, dims= [64, 128, 320, 512]):
        super(Net, self).__init__()

        self.encoder = Encoder()

        self.encoder_shaper_8 = nn.Sequential(nn.LayerNorm(512), nn.Linear(512, 512), nn.GELU())
        self.encoder_shaper_16 = nn.Sequential(nn.LayerNorm(320), nn.Linear(320, 320), nn.GELU())
        self.encoder_shaper_32 = nn.Sequential(nn.LayerNorm(128), nn.Linear(128, 128), nn.GELU())
        self.encoder_shaper_64 = nn.Sequential(nn.LayerNorm(64), nn.Linear(64, 64), nn.GELU())

        # self.transformer = nn.ModuleList([Transformer(depth=d,
        #                                               num_heads=n,
        #                                               embed_dim=e,
        #                                               mlp_ratio=m,
        #                                               num_patches=p) for d, n, e, m, p in opt.transformer])

        self.p = 8
        self.p2 = 16
        self.p3 = 32
        self.p4 = 64
        c1_in_channels, c2_in_channels, c3_in_channels, c4_in_channels = dims[0], dims[1], dims[2], dims[3]
        
        self.GLSA_c4 = GLSA(input_dim=c4_in_channels, embed_dim=dim)
        self.GLSA_c3 = GLSA(input_dim=c3_in_channels, embed_dim=dim)
        self.GLSA_c2 = GLSA(input_dim=c2_in_channels, embed_dim=dim)
        self.L_feature = BasicConv2d(c1_in_channels,dim, 3,1,1)
        
        self.SBA = SBA(input_dim = dim)
        self.fuse = BasicConv2d(dim * 2, dim, 1)
        self.fuse2 = nn.Sequential(BasicConv2d(dim*3, dim, 1,1),nn.Conv2d(dim, 1, kernel_size=1, bias=False))
        # self.EnhancedMultiScaleRefiner = EnhancedMultiScaleRefiner(channels=1)
        # self.fuse2 = nn.Sequential(
        #             BasicConv2d(dim*3, dim, 1, 1),
        #             nn.Conv2d(dim, num_classes, kernel_size=1, bias=False)
        #         )
        
        ######
        
        self.efm1 = EFM(64)
        self.efm2 = EFM(128)
        self.efm3 = EFM(320)
        self.efm4 = EFM(512)

        self.reduce1 = Conv1x1(64, 64)
        self.reduce2 = Conv1x1(128, 128)
        self.reduce3 = Conv1x1(320, 256)
        self.reduce4 = Conv1x1(512, 256)

        self.cam1 = CAM(128, 64)
        self.cam2 = CAM(256, 128)
        self.cam3 = CAM(256, 256)
        
        
        self.proj_c4 = nn.Conv2d(512, 32, kernel_size=1)
        self.proj_c3 = nn.Conv2d(320, 32, kernel_size=1)
        self.proj_c2 = nn.Conv2d(128, 32, kernel_size=1)

        self.predictor1 = nn.Conv2d(64, 1, 1)
        self.predictor2 = nn.Conv2d(128, 1, 1)
        self.predictor3 = nn.Conv2d(256, 1, 1)
        # self.edge_to_8c = nn.Conv2d(1, 1, kernel_size=1, bias=False)



    def forward(self, x):
        B = x.shape[0]
        # PVT encoder
        out_8r, out_16r, out_32r, out_64r = self.encoder(x)
        pred = list()

        # out_8, out_16, out_32, out_64 = [tf(o) for tf, o, peb in zip(self.transformer,
        #                                                                   [out_8r, out_16r, out_32r, out_64r],
        #                                                                   [False, False, False,False])]  # B, patch, feature
        
        c4 = self.encoder_shaper_8(out_8r).transpose(1, 2).reshape(B, 512, self.p, self.p)
        c3 = self.encoder_shaper_16(out_16r).transpose(1, 2).reshape(B, 320, self.p * 2, self.p * 2)
        c2 = self.encoder_shaper_32(out_32r).transpose(1, 2).reshape(B, 128, self.p * 4, self.p * 4)
        c1 = self.encoder_shaper_64(out_64r).transpose(1, 2).reshape(B, 64, self.p * 8, self.p * 8)
        
        ####左边的
        n, _, h, w = c4.shape        
        _c4 = self.GLSA_c4(c4) # [1, 64, 11, 11]
        # _c4 = self.proj_c4(c4)
        _c4 = Upsample(_c4, c3.size()[2:])
        # _c3 = self.proj_c3(c3) 
        _c3 = self.GLSA_c3(c3) # [1, 64, 22, 22]
        _c2 = self.GLSA_c2(c2) # [1, 64, 44, 44]
        # _c2 = self.proj_c2(c2) 
        
        output = self.fuse2(torch.cat([Upsample(_c4, c2.size()[2:]), Upsample(_c3, c2.size()[2:]), _c2], dim=1))
        
        L_feature = self.L_feature(c1)  # [1, 64, 88, 88]
        H_feature = self.fuse(torch.cat([_c4, _c3], dim=1))
        H_feature = Upsample(H_feature,c2.size()[2:])
        

        # # 检查是否有可用 GPU，如果有就用 GPU，否则用 CPU
        # device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
        # # 1. 上采样 H_feature 到 L_feature 尺寸
        # H_feature_up = F.interpolate(H_feature, size=L_feature.shape[2:], mode='bilinear', align_corners=False)

        # # 2. 拼接 L_feature 和上采样后的 H_feature
        # fusion = torch.cat([L_feature, H_feature_up], dim=1)  # [64, 64, 64, 64]

        # # 3. 用 1x1 卷积压缩到 1 个通道
        # conv = nn.Conv2d(fusion.size(1), 1, kernel_size=1).to(device)
        # edge = conv(fusion)  # [64, 1, 64, 64]
    
        edge = self.SBA(H_feature,L_feature)
        # viz_data = {
        #     'input': x.detach().cpu(),
        #     'H_feature': H_feature.detach().cpu(),
        #     'L_feature': L_feature.detach().cpu(),
        #     'raw_edge': edge.detach().cpu(),  # SBA原始输出
        #     'edge_att': torch.sigmoid(edge).detach().cpu()  # 激活后的边缘图
        # }
        
        output = F.interpolate(output, scale_factor=8, mode='bilinear')
        # output1 = self.edge_to_8c(edge)
        output1 = F.interpolate(edge, scale_factor=4, mode='bilinear')
        pred.append(output)
        pred.append(output1)
        edge_att = torch.sigmoid(edge)
        
        
        
        
        ###开始进行右边的分支
        x1, x2, x3, x4 = c1,c2,c3,c4
        x1a = self.efm1(x1, edge_att)
        x2a = self.efm2(x2, edge_att)
        x3a = self.efm3(x3, edge_att)
        x4a = self.efm4(x4, edge_att)

        x1r = self.reduce1(x1a)
        x2r = self.reduce2(x2a)
        x3r = self.reduce3(x3a)
        x4r = self.reduce4(x4a)

        x34 = self.cam3(x3r, x4r)
        x234 = self.cam2(x2r, x34)
        x1234 = self.cam1(x1r, x234)

        o3 = self.predictor3(x34)
        o3 = F.interpolate(o3, scale_factor=16, mode='bilinear', align_corners=False)
        o2 = self.predictor2(x234)
        o2 = F.interpolate(o2, scale_factor=8, mode='bilinear', align_corners=False)
        o1 = self.predictor1(x1234)
        o1 = F.interpolate(o1, scale_factor=4, mode='bilinear', align_corners=False)
        #oe = F.interpolate(edge_att, scale_factor=4, mode='bilinear', align_corners=False)
        pred.append(o3)
        pred.append(o2)
        pred.append(o1)
        # pred.append(oe)
        

        return pred
