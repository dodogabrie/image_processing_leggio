const fs = require('fs').promises;
const path = require('path');
const { spawn } = require('child_process');
const os = require('os');
const { getAllFolders } = require('./utils');

module.exports = { processDir };

const MAX_PARALLEL = Math.max(2, Math.floor(os.cpus().length / 2));

function convertWithSpawn(input, output, retries = 1) {
  return new Promise((resolve, reject) => {
    const child = spawn('node', [path.join(__dirname, 'worker.js'), input, output], {
      stdio: ['ignore', 'inherit', 'inherit']
    });

    child.on('exit', code => {
      if (code === 0) return resolve();
      if (retries > 0) return resolve(convertWithSpawn(input, output, retries - 1));
      reject(new Error(`worker exited with code ${code}`));
    });
  });
}

async function processInBatches(tasks, maxParallel) {
  const results = [];
  const queue = [...tasks];
  const running = [];

  while (queue.length || running.length) {
    while (running.length < maxParallel && queue.length) {
      const task = queue.shift();
      const p = task().finally(() => {
        const i = running.indexOf(p);
        if (i !== -1) running.splice(i, 1);
      });
      running.push(p);
      results.push(p);
    }
    await Promise.race(running);
  }

  return Promise.allSettled(results);
}

async function processDir(
  dir,
  progressCallback = () => {},
  baseInput = dir,
  baseOutput = path.join(process.env.HOME || process.env.USERPROFILE, 'output', path.basename(baseInput)),
  folderInfo = null,
  shouldStopFn = () => false,
  errorFiles = null,
  isRoot = true
) {
  if (shouldStopFn()) return;

  if (!folderInfo) {
    const allFolders = await getAllFolders(baseInput);
    folderInfo = { allFolders, currentFolderIdx: 0 };
    progressCallback({
      current: 0, total: 0,
      folderIdx: 0, folderTotal: allFolders.length,
      currentFolder: '', currentFile: ''
    });
    if (shouldStopFn()) return;
    errorFiles = errorFiles || [];
  }

  folderInfo.currentFolderIdx =
    folderInfo.allFolders.findIndex(f => path.resolve(f) === path.resolve(dir)) + 1;

  const relativePath = path.relative(baseInput, dir);
  const currentOutputDir = path.join(baseOutput, relativePath);

  const entries = await fs.readdir(dir, { withFileTypes: true });
  const dirs = entries.filter(e => e.isDirectory()).map(e => e.name);
  const images = entries.filter(e => !e.isDirectory() && /\.(tif|jpe?g|png)$/i.test(e.name)).map(e => e.name);
  const xmls = entries.filter(e => !e.isDirectory() && /\.xml$/i.test(e.name)).map(e => e.name);

  const total = images.length;
  let current = 0;
  if (total > 0 || xmls.length > 0) {
    await fs.mkdir(currentOutputDir, { recursive: true });
  }

  for (const sub of dirs) {
    if (shouldStopFn()) return;
    if (sub === '$RECYCLE.BIN') continue;
    await processDir(path.join(dir, sub), progressCallback, baseInput, baseOutput, folderInfo, shouldStopFn, errorFiles, false);
  }

  const tasks = images.map(file => async () => {
    if (shouldStopFn()) return;

    const fullPath = path.join(dir, file);
    const output = path.join(currentOutputDir, file.replace(/\.\w+$/, '.webp'));

    try {
      await fs.access(output);
      current++;
      progressCallback({
        current, total,
        folderIdx: folderInfo.currentFolderIdx,
        folderTotal: folderInfo.allFolders.length,
        currentFolder: path.basename(dir),
        currentFile: file
      });
      return;
    } catch {}

    try {
      await convertWithSpawn(fullPath, output);
    } catch (err) {
      console.error('Errore convertWithSpawn:', fullPath, err.message);
      errorFiles.push(`${fullPath} - ${err.message}`);
      return;
    }

    current++;
    progressCallback({
      current, total,
      folderIdx: folderInfo.currentFolderIdx,
      folderTotal: folderInfo.allFolders.length,
      currentFolder: path.basename(dir),
      currentFile: file
    });
  });

  await processInBatches(tasks, MAX_PARALLEL);

  for (const file of xmls) {
    if (shouldStopFn()) return;
    const fullPath = path.join(dir, file);
    const output = path.join(currentOutputDir, file);
    try {
      await fs.access(output);
      continue;
    } catch {}
    try {
      await fs.copyFile(fullPath, output);
    } catch (err) {
      console.error('Errore copia XML:', fullPath, err.message);
      errorFiles.push(`${fullPath} - ${err.message}`);
    }
  }

  if (isRoot && errorFiles.length) {
    const errorFilePath = path.join(baseOutput, 'error_files.txt');
    try {
      await fs.writeFile(errorFilePath, errorFiles.join('\n'), 'utf8');
      console.log('File errori scritto in:', errorFilePath);
    } catch (err) {
      console.error('Errore scrittura file errori:', err.message);
    }
  }
}

