const fs = require('fs').promises;
const path = require('path');
const os = require('os');
const {
  cropPageWorker,
  convertWorker,
  createThumbnailWorker
} = require('./worker_forks');
const { cropWorker } = require('./workers/crop_worker'); // aggiungi questa riga
const { getAllFolders } = require('./scripts/utils');

module.exports = { processDir };

const MAX_PARALLEL = Math.max(1, Math.floor(os.cpus().length / 2));

const THUMBNAIL_ALIASES = {
  low_quality: { size: [640, 480], quality: 75, crop: false, format: 'webp' },
  gallery:     { size: [1920,1080], quality: 75, crop: false, format: 'webp' }
};

async function processInBatches(tasks, maxParallel) {
  const results = [];
  const queue = [...tasks];
  const running = [];
  while (queue.length || running.length) {
    while (running.length < maxParallel && queue.length) {
      const p = queue.shift()().finally(() => {
        running.splice(running.indexOf(p), 1);
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
  baseOutput = path.join(
    process.env.HOME || process.env.USERPROFILE,
    'output1',
    path.basename(baseInput)
  ),
  folderInfo = null,
  shouldStopFn = () => false,
  errorFiles = null,
  isRoot = true,
  crop = true // crop parameter now controlled from frontend
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
    errorFiles = [];
  }

  folderInfo.currentFolderIdx =
    folderInfo.allFolders.findIndex(f => path.resolve(f) === path.resolve(dir)) + 1;

  const relativePath = path.relative(baseInput, dir);
  const outDir = path.join(baseOutput, relativePath);
  await fs.mkdir(outDir, { recursive: true });

  const entries = await fs.readdir(dir, { withFileTypes: true });
  const dirs = entries.filter(e => e.isDirectory()).map(e => e.name);
  const images = entries
    .filter(e => !e.isDirectory() && /\.(tif|jpe?g|png)$/i.test(e.name))
    .map(e => e.name);
  const xmls = entries
    .filter(e => !e.isDirectory() && /\.xml$/i.test(e.name))
    .map(e => e.name);

  // Ricorsione su sottocartelle
  for (const sub of dirs) {
    if (shouldStopFn() || sub === '$RECYCLE.BIN') continue;
    await processDir(
      path.join(dir, sub),
      progressCallback,
      baseInput,
      baseOutput,
      folderInfo,
      shouldStopFn,
      errorFiles,
      false,
      crop
    );
  }

  // Processa immagini
  if (images.length) {
    let current = 0;
    const tasks = images.map(file => async () => {
      if (shouldStopFn()) return;
      const src = path.join(dir, file);
      const dest = path.join(outDir, file.replace(/\.\w+$/, '.webp'));
      let skip = false;
      try {
        if ((await fs.stat(dest)).size > 0) skip = true;
        else await fs.unlink(dest);
      } catch {}
      if (!skip) {
        try {
          await convertWorker(src, dest);
          if (crop) {
            const thumbsBaseCrop = path.join(baseOutput, 'thumbnails', relativePath);
            const cropDest = path.join(
              thumbsBaseCrop,
              path.basename(dest, '.webp') + `_book.webp`
            );
            await cropWorker(dest, cropDest);
          }
        } catch (e) {
          errorFiles.push(`${src} - ${e.message}`);
          return;
        }
      }
      // Thumbnails
      const thumbsBase = path.join(baseOutput, 'thumbnails', relativePath);
      await fs.mkdir(thumbsBase, { recursive: true });
      for (const alias of Object.keys(THUMBNAIL_ALIASES)) {
        const thumbPath = path.join(
          thumbsBase,
          path.basename(dest, '.webp') + `_${alias}.webp`
        );
        try {
          await createThumbnailWorker(
            dest,
            thumbPath,
            JSON.stringify(THUMBNAIL_ALIASES[alias])
          );
        } catch (e) {
          errorFiles.push(`${dest} (${alias}) - ${e.message}`);
        }
      }
      current++;
      progressCallback({
        current,
        total: images.length,
        folderIdx: folderInfo.currentFolderIdx,
        folderTotal: folderInfo.allFolders.length,
        currentFolder: path.basename(dir),
        currentFile: file
      });
    });

    await processInBatches(tasks, MAX_PARALLEL);
  }

  // Copia XML
  for (const file of xmls) {
    if (shouldStopFn()) break;
    const src = path.join(dir, file);
    const dest = path.join(outDir, file);
    try {
      await fs.copyFile(src, dest);
    } catch (e) {
      errorFiles.push(`${src} - ${e.message}`);
    }
  }

  // Scrivi lista errori
  if (isRoot && errorFiles.length) {
    await fs.writeFile(
      path.join(baseOutput, 'error_files.txt'),
      errorFiles.join('\n')
    );
  }
}
