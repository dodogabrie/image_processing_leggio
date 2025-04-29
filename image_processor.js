const fs = require('fs').promises;
const path = require('path');
const sharp = require('sharp');
const { getAllFolders } = require('./utils');

module.exports = { processDir };

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

  // Solo la prima chiamata: raccogli tutte le cartelle e inizializza errorFiles
  if (!folderInfo) {
    const allFolders = await getAllFolders(baseInput);
    folderInfo = {
      allFolders,
      currentFolderIdx: 0
    };
    progressCallback({
      current: 0,
      total: 0,
      folderIdx: 0,
      folderTotal: allFolders.length,
      currentFolder: '',
      currentFile: ''
    });
    if (shouldStopFn()) return;
    if (!errorFiles) errorFiles = [];
  }

  // Aggiorna l'indice della cartella corrente
  folderInfo.currentFolderIdx = folderInfo.allFolders.findIndex(f => path.resolve(f) === path.resolve(dir)) + 1;

  const relativePath = path.relative(baseInput, dir);
  const currentOutputDir = path.join(baseOutput, relativePath);

  const files = await fs.readdir(dir);
  const images = files.filter(file => /\.(tif|jpg|jpeg|png)$/i.test(file));
  const xmls = files.filter(file => /\.xml$/i.test(file));

  let hasWork = images.length > 0 || xmls.length > 0;
  let current = 0;
  const total = images.length;

  if (hasWork) {
    await fs.mkdir(currentOutputDir, { recursive: true });
  }

  // Prima processa le sottocartelle
  for (const file of files) {
    if (shouldStopFn()) return;
    const fullPath = path.join(dir, file);
    if (file === '$RECYCLE.BIN') continue;
    const stat = await fs.stat(fullPath);

    if (stat.isDirectory()) {
      await processDir(fullPath, progressCallback, baseInput, baseOutput, folderInfo, shouldStopFn, errorFiles, false);
      if (shouldStopFn()) return;
    }
  }

  // Processa immagini una alla volta (sequenziale)
  for (const file of images) {
    if (shouldStopFn()) return;
    const fullPath = path.join(dir, file);
    const output = path.join(currentOutputDir, path.basename(fullPath).replace(/\.\w+$/, '.webp'));
    let skip = false;
    try {
      await fs.access(output);
      skip = true;
    } catch {
      // file non esiste, va processato
    }
    if (skip) {
      current++;
      progressCallback({
        current,
        total,
        folderIdx: folderInfo.currentFolderIdx,
        folderTotal: folderInfo.allFolders.length,
        currentFolder: path.basename(dir),
        currentFile: file
      });
      continue;
    }
    try {
      await sharp(fullPath)
        .withMetadata()
        .webp({ quality: 20 })
        .toFile(output);
    } catch (err) {
      console.error('Errore sharp:', fullPath, err);
      errorFiles && errorFiles.push(fullPath + ' - ' + err.message);
      continue;
    }
    current++;
    progressCallback({
      current,
      total,
      folderIdx: folderInfo.currentFolderIdx,
      folderTotal: folderInfo.allFolders.length,
      currentFolder: path.basename(dir),
      currentFile: file
    });
  }

  // Processa XML come prima
  for (const file of xmls) {
    if (shouldStopFn()) return;
    const fullPath = path.join(dir, file);
    const output = path.join(currentOutputDir, path.basename(fullPath));
    try {
      await fs.access(output);
      continue;
    } catch {}
    try {
      await fs.copyFile(fullPath, output);
    } catch (err) {
      console.error('Errore copia XML:', fullPath, err);
      errorFiles && errorFiles.push(fullPath + ' - ' + err.message);
    }
  }

  // Alla fine della chiamata root, scrivi il file di errori se ce ne sono
  if (isRoot && errorFiles && errorFiles.length > 0) {
    const errorFilePath = path.join(baseOutput, 'error_files.txt');
    try {
      await fs.writeFile(errorFilePath, errorFiles.join('\n'), 'utf8');
      console.log('File errori scritto in:', errorFilePath);
    } catch (err) {
      console.error('Errore scrittura file errori:', err);
    }
  }
}
