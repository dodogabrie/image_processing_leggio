const fs = require('fs').promises;
const path = require('path');
const os = require('os');
const { spawn, fork } = require('child_process');
const { getAllFolders } = require('./scripts/utils');

module.exports = { processDir };

const MAX_PARALLEL = Math.max(1, Math.floor(os.cpus().length / 2));

const THUMBNAIL_ALIASES = {
  low_quality: { size: [640, 480], quality: 75, crop: false, format: 'webp' },
  gallery:     { size: [1920,1080], quality: 75, crop: false, format: 'webp' }
};

function cropPageWithSpawn(input, output, minArea = 200000) {
  const pythonPath = process.platform === 'win32'
    ? path.join(__dirname, 'venv', 'Scripts', 'python.exe')
    : path.join(__dirname, 'venv', 'bin', 'python3');
  const scriptPath = path.join(__dirname, 'scripts', 'crop.py');

  return new Promise((resolve, reject) => {
    const child = spawn(pythonPath, [ scriptPath, input, output, String(minArea) ], {
      stdio: ['ignore','pipe','pipe']
    });
    child.stdout.on('data', d => process.stdout.write(d));
    child.stderr.on('data', d => process.stderr.write(d));
    child.on('exit', code => {
      if (code === 0) return resolve(true);
      if (code === 2) return resolve(false);
      reject(new Error(`crop.py exited with code ${code}`));
    });
  });
}

function convertWithSpawn(input, output, retries = 1) {
  return new Promise((resolve, reject) => {
    const child = fork(
      path.join(__dirname, 'workers', 'worker.js'),
      [ input, output ],
      {
        execPath: process.env.NODE_ENV === 'development' ? 'node' : process.execPath,
        stdio: ['ignore','pipe','pipe','ipc'],
        windowsHide: true
      }
    );
    child.stdout.on('data', d => process.stdout.write(d.toString()));
    child.stderr.on('data', d => process.stderr.write(d.toString()));
    child.on('exit', code => {
      if (code === 0) return resolve();
      if (retries > 0) return resolve(convertWithSpawn(input, output, retries - 1));
      reject(new Error(`worker exited with code ${code}`));
    });
  });
}

function createThumbnailWithSpawn(input, output, alias) {
  return new Promise((resolve, reject) => {
    const child = fork(
      path.join(__dirname, 'workers', 'thumbnail_worker.js'),
      [ input, output, JSON.stringify(THUMBNAIL_ALIASES[alias]) ],
      {
        execPath: process.env.NODE_ENV === 'development' ? 'node' : process.execPath,
        stdio: ['ignore','pipe','pipe','ipc'],
        windowsHide: true
      }
    );
    child.stdout.on('data', d => process.stdout.write(d.toString()));
    child.stderr.on('data', d => process.stderr.write(d.toString()));
    child.on('exit', code => {
      if (code === 0) return resolve();
      reject(new Error(`thumbnail_worker exited with code ${code}`));
    });
  });
}

async function processInBatches(tasks, maxParallel) {
  const results = [];
  const queue = [...tasks];
  const running = [];
  while (queue.length || running.length) {
    while (running.length < maxParallel && queue.length) {
      const p = queue.shift()().finally(() => {
        running.splice(running.indexOf(p),1);
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
  baseOutput = path.join(process.env.HOME||process.env.USERPROFILE,'output1',path.basename(baseInput)),
  folderInfo = null,
  shouldStopFn = () => false,
  errorFiles = null,
  isRoot = true,
  testOnly = false
) {
  if (shouldStopFn()) return;
  if (!folderInfo) {
    const allFolders = await getAllFolders(baseInput);
    folderInfo = { allFolders, currentFolderIdx: 0 };
    progressCallback({ current:0,total:0,folderIdx:0,folderTotal:allFolders.length,currentFolder:'',currentFile:'' });
    errorFiles = [];
  }
  folderInfo.currentFolderIdx = folderInfo.allFolders.findIndex(f => path.resolve(f)===path.resolve(dir)) + 1;
  const relativePath = path.relative(baseInput, dir);
  const outDir = path.join(baseOutput, relativePath);
  await fs.mkdir(outDir, { recursive: true });

  const entries = await fs.readdir(dir, { withFileTypes: true });
  const dirs   = entries.filter(e=>e.isDirectory()).map(e=>e.name);
  const images = entries.filter(e=>!e.isDirectory() && /\.(tif|jpe?g|png)$/i.test(e.name)).map(e=>e.name);
  const xmls   = entries.filter(e=>!e.isDirectory() && /\.xml$/i.test(e.name)).map(e=>e.name);

  for (const sub of dirs) {
    if (shouldStopFn()||sub==='$RECYCLE.BIN') continue;
    await processDir(path.join(dir,sub),progressCallback,baseInput,baseOutput,folderInfo,shouldStopFn,errorFiles,false,testOnly);
  }

  if (images.length) {
    let current = 0;
    const tasks = images.map(file => async () => {
      if (shouldStopFn()) return;
      const src = path.join(dir,file);
      const dest = path.join(outDir, file.replace(/\.\w+$/,'.webp'));
      let skip=false;
      try {
        if ((await fs.stat(dest)).size>0) skip=true;
        else await fs.unlink(dest);
      } catch {}
      if (!skip) {
        try { await convertWithSpawn(src,dest); }
        catch (e) { errorFiles.push(`${src} - ${e.message}`); return; }
      }
      const thumbsBase = path.join(baseOutput,'thumbnails',relativePath);
      await fs.mkdir(thumbsBase,{ recursive:true });
      for (const alias of Object.keys(THUMBNAIL_ALIASES)) {
        const thumb = path.join(thumbsBase, path.basename(dest,'.webp')+`_${alias}.webp`);
        try { await createThumbnailWithSpawn(dest,thumb,alias); }
        catch(e){ errorFiles.push(`${dest} (${alias}) - ${e.message}`); }
      }
      current++;
      progressCallback({
        current, total: images.length,
        folderIdx: folderInfo.currentFolderIdx,
        folderTotal: folderInfo.allFolders.length,
        currentFolder: path.basename(dir),
        currentFile: file
      });
    });
    if (testOnly) {
      for (const file of images.slice(0,5)) {
        const src = path.join(dir,file);
        const dest = path.join(outDir,file.replace(/\.\w+$/,'.webp'));
        await convertWithSpawn(src,dest);
        await cropPageWithSpawn(dest, dest.replace('.webp','_crop.webp'));
      }
    } else {
      await processInBatches(tasks, MAX_PARALLEL);
    }
  }

  for (const file of xmls) {
    if (shouldStopFn()) break;
    const src = path.join(dir,file);
    const dest = path.join(outDir,file);
    try { await fs.copyFile(src,dest); }
    catch(e){ errorFiles.push(`${src} - ${e.message}`); }
  }

  if (isRoot && errorFiles.length) {
    await fs.writeFile(path.join(baseOutput,'error_files.txt'), errorFiles.join('\n'));
  }
}
