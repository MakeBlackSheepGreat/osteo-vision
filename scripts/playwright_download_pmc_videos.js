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
  ["PMC10547659_ESM1", "https://pmc.ncbi.nlm.nih.gov/articles/PMC10547659/", "https://pmc.ncbi.nlm.nih.gov/articles/instance/10547659/bin/13089_2023_339_MOESM1_ESM.mp4", "osteomyelitis_pmc/PMC10547659_osteomyelitis_ultrasound/13089_2023_339_MOESM1_ESM.mp4"],
  ["PMC12078111_S001", "https://pmc.ncbi.nlm.nih.gov/articles/PMC12078111/", "https://pmc.ncbi.nlm.nih.gov/articles/instance/12078111/bin/jprs-02-04-0150-s001.mp4", "osteomyelitis_pmc/PMC12078111_calcaneal_osteomyelitis/jprs-02-04-0150-s001.mp4"],
  ["PMC12456365_V1", "https://pmc.ncbi.nlm.nih.gov/articles/PMC12456365/", "https://pmc.ncbi.nlm.nih.gov/articles/instance/12456365/bin/JDRS-2025-36-3-763-771-V1.mp4", "osteomyelitis_pmc/PMC12456365_metacarpal_osteomyelitis/JDRS-2025-36-3-763-771-V1.mp4"],
  ["PMC12879947_S001", "https://pmc.ncbi.nlm.nih.gov/articles/PMC12879947/", "https://pmc.ncbi.nlm.nih.gov/articles/instance/12879947/bin/gox-14-e7440-s001.mp4", "osteomyelitis_pmc/PMC12879947_chronic_osteomyelitis_reconstruction/gox-14-e7440-s001.mp4"],
  ["PMC12914110_MMC1", "https://pmc.ncbi.nlm.nih.gov/articles/PMC12914110/", "https://pmc.ncbi.nlm.nih.gov/articles/instance/12914110/bin/mmc1.mp4", "osteomyelitis_pmc/PMC12914110_mucormycotic_osteomyelitis/mmc1.mp4"],
  ["PMC12914110_MMC2", "https://pmc.ncbi.nlm.nih.gov/articles/PMC12914110/", "https://pmc.ncbi.nlm.nih.gov/articles/instance/12914110/bin/mmc2.mp4", "osteomyelitis_pmc/PMC12914110_mucormycotic_osteomyelitis/mmc2.mp4"],
  ["PMC4405963_V002", "https://pmc.ncbi.nlm.nih.gov/articles/PMC4405963/", "https://pmc.ncbi.nlm.nih.gov/articles/instance/4405963/bin/NJMS-5-188-v002.flv", "osteomyelitis_pmc/PMC4405963_maxilla_tuberculous_osteomyelitis/NJMS-5-188-v002.flv"],
];

function selectedRecords() {
  const ids = new Set(process.argv.slice(2));
  return ids.size ? records.filter((record) => ids.has(record[0])) : records;
}

async function main() {
  const headless = process.env.PW_HEADLESS !== "0";
  const browser = await chromium.launch({ headless, channel: "msedge" });
  const context = await browser.newContext({ acceptDownloads: true });
  const page = await context.newPage();
  for (const [id, pageUrl, downloadUrl, localRel] of selectedRecords()) {
    const target = path.join(rawRoot, localRel);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    if (fs.existsSync(target) && fs.statSync(target).size > 100000) {
      console.log(`exists ${id} ${fs.statSync(target).size}`);
      continue;
    }
    console.log(`download ${id}`);
    await page.goto(pageUrl, { waitUntil: "domcontentloaded", timeout: 120000 });
    await page.waitForTimeout(1000);
    const hrefPath = new URL(downloadUrl).pathname;
    const downloadPromise = page.waitForEvent("download", { timeout: 60000 });
    const link = page.locator(`a[href="${hrefPath}"]`).first();
    if (await link.count()) {
      await link.click();
    } else {
      await page.goto(downloadUrl, { waitUntil: "domcontentloaded", timeout: 120000 }).catch(() => undefined);
    }
    const download = await downloadPromise.catch(async (error) => {
      console.log(`download timeout ${id}: ${error.message}`);
      console.log(`page ${page.url()} ${await page.title()}`);
      const text = (await page.locator("body").innerText().catch(() => "")).slice(0, 300);
      console.log(text);
      return null;
    });
    if (!download) continue;
    await download.saveAs(target);
    console.log(`saved ${id} ${fs.statSync(target).size}`);
  }
  await browser.close();
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
