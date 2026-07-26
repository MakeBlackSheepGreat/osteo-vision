import type { AppIconName } from "@/components/appIcons";

export type NavigationGroupKey = "clinical" | "data" | "engineering";

export interface NavigationItem {
  to: string;
  label: string;
  icon: AppIconName;
  group: NavigationGroupKey;
  order: number;
}

export interface NavigationGroup {
  key: NavigationGroupKey;
  label: string;
  items: NavigationItem[];
}

export const navigationGroups: NavigationGroup[] = [
  {
    key: "clinical",
    label: "病例工作流",
    items: [
      { to: "/intake", label: "数据准入", icon: "shield", group: "clinical", order: 10 },
      { to: "/cases", label: "病例档案", icon: "case", group: "clinical", order: 20 },
      { to: "/case", label: "病例工作台", icon: "target", group: "clinical", order: 30 },
      { to: "/navigation", label: "三维导航", icon: "cube", group: "clinical", order: 40 },
      { to: "/review", label: "医生复核", icon: "review", group: "clinical", order: 50 },
      { to: "/report", label: "报告导出", icon: "report", group: "clinical", order: 60 },
    ],
  },
  {
    key: "data",
    label: "数据与标注",
    items: [
      { to: "/data", label: "视频库", icon: "video", group: "data", order: 70 },
      { to: "/dataset-review", label: "静态数据复核", icon: "database", group: "data", order: 80 },
      { to: "/annotations", label: "人工标注", icon: "brush", group: "data", order: 90 },
    ],
  },
  {
    key: "engineering",
    label: "三维与展示",
    items: [{ to: "/showcase", label: "工程展示", icon: "layers", group: "engineering", order: 100 }],
  },
];

export const navigationItems = navigationGroups.flatMap((group) => group.items);

export const navigationMetaByPath = Object.fromEntries(
  navigationItems.map((item) => [
    item.to,
    {
      label: item.label,
      icon: item.icon,
      group: item.group,
      order: item.order,
    },
  ]),
);
