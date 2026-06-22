export type AppIconName =
  | "case"
  | "review"
  | "report"
  | "plus"
  | "load"
  | "folder"
  | "upload"
  | "play"
  | "download"
  | "expand"
  | "close"
  | "clipboard"
  | "layers"
  | "target"
  | "document"
  | "file"
  | "check"
  | "alert"
  | "camera"
  | "video"
  | "stop";

export const appIconSvg: Record<AppIconName, string> = {
  case: '<rect x="4" y="4" width="16" height="16" rx="2.2" /><path d="M8 8h8M8 12h8M8 16h5" />',
  review: '<circle cx="12" cy="12" r="9" /><path d="m8 12 2.5 2.5L16.5 8.5" />',
  report: '<path d="M14 3.5H7a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-10z" /><path d="M14 3.5v5h5M8.5 12h7M8.5 15.5h7M8.5 19h4" />',
  plus: '<path d="M12 5v14M5 12h14" />',
  load: '<path d="M20 12a8 8 0 0 1-13.7 5.7" /><path d="M4 12a8 8 0 0 1 13.7-5.7" /><path d="M18 3v4h-4M6 21v-4h4" />',
  folder: '<path d="M3.5 7.5a2 2 0 0 1 2-2h4l2 2h7a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z" />',
  upload: '<path d="M12 16V5" /><path d="m7 10 5-5 5 5" /><path d="M5 19h14" />',
  play: '<path d="M8 5.5v13l10-6.5z" />',
  download: '<path d="M12 5v11" /><path d="m7 11 5 5 5-5" /><path d="M5 19h14" />',
  expand: '<path d="M8 4H4v4M16 4h4v4M20 16v4h-4M4 16v4h4" /><path d="M4 4l6 6M20 4l-6 6M20 20l-6-6M4 20l6-6" />',
  close: '<path d="M6 6l12 12M18 6 6 18" />',
  clipboard: '<path d="M9 4h6l1 2h2a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h2z" /><path d="M9 4h6v4H9z" />',
  layers: '<path d="m12 3 9 5-9 5-9-5z" /><path d="m3 12 9 5 9-5" /><path d="m3 16 9 5 9-5" />',
  target: '<circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="4.5" /><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3" />',
  document: '<path d="M14 3.5H7a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-10z" /><path d="M14 3.5v5h5M8.5 12.5h7M8.5 16h7" />',
  file: '<path d="M14 3.5H7a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-10z" /><path d="M14 3.5v5h5" />',
  check: '<circle cx="12" cy="12" r="9" /><path d="m8 12 2.5 2.5L16.5 8.5" />',
  alert: '<path d="M12 3.5 21 19H3z" /><path d="M12 9v4M12 16.5h.01" />',
  camera: '<rect x="4.5" y="8" width="15" height="10.5" rx="2.2" /><path d="M9 8l1.2-2h3.6L15 8" /><circle cx="12" cy="13.25" r="3" /><path d="M17 10.25h.01" />',
  video: '<rect x="4" y="6" width="11" height="12" rx="2" /><path d="m15 10 5-3v10l-5-3z" />',
  stop: '<rect x="7" y="7" width="10" height="10" rx="1.8" />',
};
