import fs from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const playwrightPackagePath = path.resolve(
  process.cwd(),
  '..',
  'chinese_chr_app',
  'chinese_chr_app',
  'frontend',
  'node_modules',
  'playwright',
);
const { chromium } = require(playwrightPackagePath);

const DEFAULT_SPREADSHEET_ID = '160N1gawZk8PXr2Wqwvqln88YEIl2gsnYrmeCP1TCCf0';
const DEFAULT_SHEET_NAME = 'Minecraft Coding Fundamentals';
const DEFAULT_RANGE = 'A2:E';
const DEFAULT_OUTPUT_DIR = path.resolve(process.cwd(), 'downloads', 'minecraft-supporting-files');
const DEFAULT_TIMEOUT_MS = 60_000;
const DEFAULT_DOWNLOAD_LINK_TIMEOUT_MS = 3_000;
let activeBrowser = null;
let shuttingDown = false;

function printHelp() {
  console.log(`Usage: node scripts/download_minecraft_supporting_files.mjs [options]

Downloads the ZIP from the "Download all" link for each lesson URL in a Google Sheet.

Options:
  --spreadsheet-id <id>   Spreadsheet ID to read from
  --sheet-name <name>     Sheet/tab name to read from
  --range <range>         A:E-style range within the tab (default: ${DEFAULT_RANGE})
  --output-dir <dir>      Directory to save ZIP files into
  --limit <n>             Process only the first n lesson rows
  --headed                Run Chromium in headed mode
  --dry-run               Print the lesson rows without downloading
  --timeout-ms <ms>       Per-page timeout in milliseconds
  --download-link-timeout-ms <ms>
                          How long to wait for "Download all"
  --help                  Show this help

Examples:
  node scripts/download_minecraft_supporting_files.mjs --headed
  node scripts/download_minecraft_supporting_files.mjs --limit 3 --dry-run
  node scripts/download_minecraft_supporting_files.mjs --output-dir ~/Downloads/minecraft-zips
`);
}

function parseArgs(argv) {
  const options = {
    spreadsheetId: DEFAULT_SPREADSHEET_ID,
    sheetName: DEFAULT_SHEET_NAME,
    range: DEFAULT_RANGE,
    outputDir: DEFAULT_OUTPUT_DIR,
    limit: null,
    headed: false,
    dryRun: false,
    timeoutMs: DEFAULT_TIMEOUT_MS,
    downloadLinkTimeoutMs: DEFAULT_DOWNLOAD_LINK_TIMEOUT_MS,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    const next = argv[index + 1];

    if (arg === '--help') {
      printHelp();
      process.exit(0);
    }

    if (arg === '--headed') {
      options.headed = true;
      continue;
    }

    if (arg === '--dry-run') {
      options.dryRun = true;
      continue;
    }

    if (arg === '--spreadsheet-id' && next) {
      options.spreadsheetId = next;
      index += 1;
      continue;
    }

    if (arg === '--sheet-name' && next) {
      options.sheetName = next;
      index += 1;
      continue;
    }

    if (arg === '--range' && next) {
      options.range = next;
      index += 1;
      continue;
    }

    if (arg === '--output-dir' && next) {
      options.outputDir = expandHome(next);
      index += 1;
      continue;
    }

    if (arg === '--limit' && next) {
      options.limit = Number.parseInt(next, 10);
      index += 1;
      continue;
    }

    if (arg === '--timeout-ms' && next) {
      options.timeoutMs = Number.parseInt(next, 10);
      index += 1;
      continue;
    }

    if (arg === '--download-link-timeout-ms' && next) {
      options.downloadLinkTimeoutMs = Number.parseInt(next, 10);
      index += 1;
      continue;
    }

    throw new Error(`Unknown or incomplete argument: ${arg}`);
  }

  if (options.limit !== null && (!Number.isInteger(options.limit) || options.limit <= 0)) {
    throw new Error('--limit must be a positive integer');
  }

  if (!Number.isInteger(options.timeoutMs) || options.timeoutMs <= 0) {
    throw new Error('--timeout-ms must be a positive integer');
  }

  if (!Number.isInteger(options.downloadLinkTimeoutMs) || options.downloadLinkTimeoutMs <= 0) {
    throw new Error('--download-link-timeout-ms must be a positive integer');
  }

  return options;
}

function expandHome(value) {
  if (!value.startsWith('~/')) {
    return value;
  }

  const home = process.env.HOME;
  if (!home) {
    throw new Error('Cannot expand ~/ because HOME is not set');
  }

  return path.join(home, value.slice(2));
}

function runGws(spreadsheetId, sheetName, range) {
  const params = JSON.stringify({
    spreadsheetId,
    range: `'${sheetName}'!${range}`,
  });

  const result = spawnSync(
    'gws',
    ['sheets', 'spreadsheets', 'values', 'get', '--params', params],
    {
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'pipe'],
    },
  );

  if (result.status !== 0) {
    const stderr = result.stderr.trim();
    throw new Error(`gws command failed${stderr ? `: ${stderr}` : ''}`);
  }

  return JSON.parse(result.stdout);
}

function sanitizeFilePart(value) {
  return value
    .replace(/[^a-z0-9]+/gi, '-')
    .replace(/^-+|-+$/g, '')
    .toLowerCase();
}

function buildLessons(values, limit) {
  const rows = values ?? [];
  const lessons = rows
    .map((row, index) => {
      const [block = '', lesson = '', name = '', scope = '', url = ''] = row;

      if (!url) {
        return null;
      }

      return {
        rowNumber: index + 2,
        block,
        lesson,
        name,
        scope,
        url,
      };
    })
    .filter(Boolean);

  return limit === null ? lessons : lessons.slice(0, limit);
}

function buildOutputName(lesson, suggestedFilename) {
  const extension = path.extname(suggestedFilename) || '.zip';
  const stemParts = [lesson.block, lesson.lesson, lesson.name]
    .filter(Boolean)
    .map(sanitizeFilePart)
    .filter(Boolean);
  const stem = stemParts.length > 0 ? stemParts.join('__') : `row-${lesson.rowNumber}`;
  return `${stem}${extension}`;
}

async function uniquePath(filePath) {
  const directory = path.dirname(filePath);
  const extension = path.extname(filePath);
  const stem = path.basename(filePath, extension);

  let candidate = filePath;
  let counter = 2;

  while (true) {
    try {
      await fs.access(candidate);
      candidate = path.join(directory, `${stem}__${counter}${extension}`);
      counter += 1;
    } catch {
      return candidate;
    }
  }
}

async function waitForDownloadLink(page, timeoutMs) {
  const candidateSelectors = [
    page.getByRole('link', { name: /download all/i }),
    page.getByText(/download all/i),
    page.locator('a:has-text("Download all")'),
  ];

  for (const locator of candidateSelectors) {
    if ((await locator.first().count()) > 0) {
      return locator.first();
    }
  }

  for (const locator of candidateSelectors) {
    try {
      await locator.first().waitFor({ state: 'visible', timeout: timeoutMs });
      return locator.first();
    } catch {
      continue;
    }
  }

  throw new Error('Could not find a visible "Download all" link');
}

async function downloadLessonZip(browserContext, lesson, options) {
  const page = await browserContext.newPage();

  try {
    console.log(`Opening row ${lesson.rowNumber}: ${lesson.name}`);
    await page.goto(lesson.url, { waitUntil: 'domcontentloaded', timeout: options.timeoutMs });
    await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {});

    let downloadLink;
    try {
      downloadLink = await waitForDownloadLink(page, options.downloadLinkTimeoutMs);
    } catch (error) {
      console.warn(`  skipped ${lesson.name}: ${error.message}`);
      return { status: 'skipped', lesson };
    }

    if (options.dryRun) {
      console.log(`  found Download all on ${lesson.url}`);
      return { status: 'dry-run', lesson };
    }

    const downloadPromise = page.waitForEvent('download', { timeout: options.timeoutMs });
    await downloadLink.click();
    const download = await downloadPromise;
    const fileName = buildOutputName(lesson, download.suggestedFilename());
    const targetPath = await uniquePath(path.join(options.outputDir, fileName));
    await download.saveAs(targetPath);
    console.log(`  saved ${path.relative(process.cwd(), targetPath)}`);
    return { status: 'downloaded', lesson, targetPath };
  } finally {
    await page.close();
  }
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const response = runGws(options.spreadsheetId, options.sheetName, options.range);
  const lessons = buildLessons(response.values, options.limit);

  if (lessons.length === 0) {
    console.log('No lesson URLs found for the requested range.');
    return;
  }

  console.log(`Found ${lessons.length} lesson URL(s) in ${options.sheetName}.`);

  if (options.dryRun) {
    for (const lesson of lessons) {
      console.log(`- row ${lesson.rowNumber}: ${lesson.name} -> ${lesson.url}`);
    }
  }

  await fs.mkdir(options.outputDir, { recursive: true });

  const browser = await chromium.launch({
    args: ['--disable-http2'],
    headless: !options.headed,
  });
  activeBrowser = browser;

  const context = await browser.newContext({
    acceptDownloads: true,
  });

  try {
    const results = [];
    for (const lesson of lessons) {
      results.push(await downloadLessonZip(context, lesson, options));
    }

    const downloadedCount = results.filter((result) => result?.status === 'downloaded').length;
    const skippedCount = results.filter((result) => result?.status === 'skipped').length;

    if (!options.dryRun) {
      console.log(`Finished: ${downloadedCount} downloaded, ${skippedCount} skipped.`);
    }
  } finally {
    await context.close();
    await browser.close();
    activeBrowser = null;
  }
}

async function closeActiveBrowser() {
  if (!activeBrowser || shuttingDown) {
    return;
  }

  shuttingDown = true;

  try {
    await activeBrowser.close();
  } catch {
    // Ignore shutdown-time browser close errors.
  } finally {
    activeBrowser = null;
    shuttingDown = false;
  }
}

for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => {
    void closeActiveBrowser().finally(() => {
      process.exit(130);
    });
  });
}

process.on('exit', () => {
  if (activeBrowser && !shuttingDown) {
    try {
      activeBrowser.close();
    } catch {
      // Ignore best-effort cleanup during process exit.
    }
  }
});

main().catch((error) => {
  console.error(error.message);
  void closeActiveBrowser().finally(() => {
    process.exit(1);
  });
});
