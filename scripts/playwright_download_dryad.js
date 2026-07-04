const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const projectRoot = path.resolve(__dirname, "..");
const rawRoot = path.join(
  projectRoot,
  "research",
  "datasets",
  "public-candidates",
  "d046_fluorescence_osteomyelitis_videos",
  "raw",
);

const records = [
  {
    id: "DRYAD_OFDVDNET_DATA",
    page: "https://datadryad.org/dataset/doi:10.5061/dryad.v6wwpzh3w",
    url: "https://datadryad.org/downloads/file_stream/3078626",
    local: "fluorescence_proxy/ofdvdnet_dryad_v6wwpzh3w/data.zip",
  },
  {
    id: "DRYAD_OFDVDNET_README",
    page: "https://datadryad.org/dataset/doi:10.5061/dryad.v6wwpzh3w",
    url: "https://datadryad.org/downloads/file_stream/3082579",
    local: "fluorescence_proxy/ofdvdnet_dryad_v6wwpzh3w/README.md",
  },
  {
    id: "DRYAD_FGS_DATA_MODELS",
    page: "https://datadryad.org/dataset/doi:10.5061/dryad.8gtht76x9",
    url: "https://datadryad.org/downloads/file_stream/3822101",
    local: "fluorescence_proxy/fgs_video_denoising_dryad_8gtht76x9/FGS_Data_and_Models.zip",
  },
  {
    id: "DRYAD_FGS_README",
    page: "https://datadryad.org/dataset/doi:10.5061/dryad.8gtht76x9",
    url: "https://datadryad.org/downloads/file_stream/3822102",
    local: "fluorescence_proxy/fgs_video_denoising_dryad_8gtht76x9/README.md",
  },
];

function selectedRecords() {
  const ids = new Set(process.argv.slice(2));
  return ids.size ? records.filter((record) => ids.has(record.id)) : records;
}

async function main() {
  const headless = process.env.PW_HEADLESS !== "0";
  const browser = await chromium.launch({ headless, channel: "msedge" });
  const context = await browser.newContext({ acceptDownloads: true });
  const page = await context.newPage();
  for (const record of selectedRecords()) {
    const target = path.join(rawRoot, record.local);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    if (fs.existsSync(target) && fs.statSync(target).size > 4096) {
      console.log(`exists ${record.id} ${fs.statSync(target).size}`);
      continue;
    }
    console.log(`download ${record.id}`);
    await page.goto(record.page, { waitUntil: "domcontentloaded", timeout: 120000 });
    await page.waitForTimeout(4000);
    const downloadPromise = page.waitForEvent("download", { timeout: 300000 });
    await page.goto(record.url, { waitUntil: "domcontentloaded", timeout: 120000 }).catch(() => undefined);
    const download = await downloadPromise.catch(async (error) => {
      console.log(`download timeout ${record.id}: ${error.message}`);
      console.log(`page ${page.url()} ${await page.title()}`);
      const text = (await page.locator("body").innerText().catch(() => "")).slice(0, 400);
      console.log(text);
      throw error;
    });
    await download.saveAs(target);
    console.log(`saved ${record.id} ${fs.statSync(target).size}`);
  }
  await browser.close();
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
