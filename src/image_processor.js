const fs = require('fs').promises;
const path = require('path');
const { spawn } = require('child_process');
const os = require('os');
const { getAllFolders } = require('./scripts/utils');

module.exports = { processDir };

const MAX_PARALLEL = Math.max(2, Math.floor(os.cpus().length / 2));

const THUMBNAIL_ALIASES = {
  low_quality: { size: [640, 480], quality: 75, crop: false, format: 'webp' },
  gallery: { size: [1920, 1080], quality: 75, crop: false, format: 'webp' }
};

function cropPageWithSpawn(input, output, minArea = 200000, logCallback) {
  const pythonPath = process.platform === 'win32'
    ? path.join(__dirname, 'venv', 'Scripts', 'python.exe')
    : path.join(__dirname, 'venv', 'bin', 'python3');
  const scriptPath = path.join(__dirname, 'scripts', 'crop.py');

  return new Promise((resolve, reject) => {
    const child = spawn(pythonPath, [scriptPath, input, output, String(minArea)], {
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: true
    });

    if (logCallback) {
      child.stdout && child.stdout.on('data', d => logCallback(d.toString()));
      child.stderr && child.stderr.on('data', d => logCallback(d.toString()));
    }

    child.on('exit', code => {
      if (code === 0) return resolve(true);
      if (code === 2) return resolve(false);
      if (logCallback) logCallback(`[ERRORE WORKER] crop.py exited with code ${code}`);
      reject(new Error(`crop.py exited with code ${code}`));
    });
  });
}

function convertWithSpawn(input, output, retries = 1, logCallback) {
  return new Promise((resolve, reject) => {
    const child = spawn('node', [path.join(__dirname, 'workers', 'worker.js'), input, output], {
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: true
    });

    if (logCallback) {
      child.stdout && child.stdout.on('data', d => logCallback(d.toString()));
      child.stderr && child.stderr.on('data', d => logCallback(d.toString()));
    }

    child.on('exit', code => {
      if (code === 0) return resolve();
      if (retries > 0) return resolve(convertWithSpawn(input, output, retries - 1, logCallback));
      if (logCallback) logCallback(`[ERRORE WORKER] worker.js exited with code ${code}`);
      reject(new Error(`worker exited with code ${code}`));
    });
  });
}

function createThumbnailWithSpawn(input, output, alias, logCallback) {
  return new Promise((resolve, reject) => {
    const args = [
      path.join(__dirname, 'workers', 'thumbnail_worker.js'),
      input,
      output,
      JSON.stringify(THUMBNAIL_ALIASES[alias])
    ];
    const child = spawn('node', args, {
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: true
    });
    if (logCallback) {
      child.stdout && child.stdout.on('data', d => logCallback(d.toString()));
      child.stderr && child.stderr.on('data', d => logCallback(d.toString()));
    }
    child.on('exit', code => {
      if (code === 0) return resolve();
      if (logCallback) logCallback(`[ERRORE WORKER] thumbnail_worker.js exited with code ${code}`);
      reject(new Error(`thumbnail_worker exited with code ${code}`));
    });
  });
}

async function runZipWorker(organizedDir, organizedThumbDir, outputZip, logCallback) {
  return new Promise((resolve, reject) => {
    const args = [
      path.join(__dirname, 'workers', 'zip_worker.js'),
      organizedDir,
      organizedThumbDir,
      outputZip
    ];
    const child = spawn('node', args, {
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: true
    });
    if (logCallback) {
      child.stdout && child.stdout.on('data', d => logCallback(d.toString()));
      child.stderr && child.stderr.on('data', d => logCallback(d.toString()));
    }
    child.on('exit', code => {
      if (code === 0) return resolve();
      if (logCallback) logCallback(`[ERRORE WORKER] zip_worker.js exited with code ${code}`);
      reject(new Error(`zip_worker exited with code ${code}`));
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
  baseOutput = path.join(process.env.HOME || process.env.USERPROFILE, 'output1', path.basename(baseInput)),
  folderInfo = null,
  shouldStopFn = () => false,
  errorFiles = null,
  isRoot = true,
  testOnly = false,
  logCallback = null
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
  const currentCroppedDir = path.join(baseOutput, relativePath);
  await fs.mkdir(currentCroppedDir, { recursive: true });

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
    await processDir(path.join(dir, sub), progressCallback, baseInput, baseOutput, folderInfo, shouldStopFn, errorFiles, false, testOnly, logCallback);
  }

  // Processa immagini in parallelo usando worker.js
  if (images.length > 0) {
    let processed = 0;
    const tasks = images.map(file => async () => {
      if (shouldStopFn()) return;
      const fullPath = path.join(dir, file);
      const output = path.join(currentOutputDir, path.basename(fullPath).replace(/\.\w+$/, '.webp'));
      let skip = false;
      try {
        // Check if output exists and is not empty
        const stat = await fs.stat(output);
        if (stat.size > 0) {
          skip = true;
        } else {
          // File exists but is empty/corrupted, delete it and recreate
          await fs.unlink(output);
        }
      } catch {
        // file non esiste, va processato
        console.log('Processing file:', fullPath);
      }
      if (!skip) {
        try {
          await convertWithSpawn(fullPath, output, 1, logCallback);
          processed++;
        } catch (err) {
          console.error('Errore worker:', fullPath, err);
          errorFiles && errorFiles.push(fullPath + ' - ' + err.message);
          return;
        }
      }
      // --- THUMBNAIL GENERATION ---
      const thumbnailsBase = path.join(baseOutput, 'thumbnails', relativePath);
      await fs.mkdir(thumbnailsBase, { recursive: true });
      for (const alias of Object.keys(THUMBNAIL_ALIASES)) {
        const thumbName = path.basename(output, '.webp') + `_${alias}.webp`;
        const thumbPath = path.join(thumbnailsBase, thumbName);
        try {
          await createThumbnailWithSpawn(output, thumbPath, alias, logCallback);
        } catch (err) {
          console.error('Errore thumbnail:', output, alias, err);
          errorFiles && errorFiles.push(output + ` (${alias}) - ` + err.message);
        }
      }
      // --- END THUMBNAIL GENERATION ---
      current++;
      progressCallback({
        current,
        total,
        folderIdx: folderInfo.currentFolderIdx,
        folderTotal: folderInfo.allFolders.length,
        currentFolder: path.basename(dir),
        currentFile: file
      });
    });

    if (testOnly) {
      const limited = images.slice(0, 5);
      for (const file of limited) {
        const fullPath = path.join(dir, file);
        const output = path.join(currentOutputDir, path.basename(fullPath).replace(/\.\w+$/, '.webp'));
        await convertWithSpawn(fullPath, output, 1, logCallback);
        const outputCropped = output.replace('.webp', '_crop.webp')
        const croppedPath = path.join(currentCroppedDir, path.basename(outputCropped));
        await cropPageWithSpawn(output, croppedPath, 200000, logCallback);
      }
    }
    else {
     await processInBatches(tasks, MAX_PARALLEL);
    }
  }

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

