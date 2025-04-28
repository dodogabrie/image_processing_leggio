const fs = require('fs');
const path = require('path');
const sharp = require('sharp');

module.exports = { processDir };

async function processDir(dir, progressCallback = () => {}, baseInput = dir, baseOutput = dir + '-processed') {
  const relativePath = path.relative(baseInput, dir);
  const currentOutputDir = path.join(baseOutput, relativePath);

  const files = fs.readdirSync(dir);
  const images = files.filter(file => /\.(tif|jpg|jpeg|png)$/i.test(file));
  const xmls = files.filter(file => /\.xml$/i.test(file));

  let hasWork = images.length > 0 || xmls.length > 0;
  let current = 0;
  const total = images.length;

  if (hasWork) {
    fs.mkdirSync(currentOutputDir, { recursive: true });
  }

  for (const file of files) {
    const fullPath = path.join(dir, file);
    const stat = fs.statSync(fullPath);

    if (stat.isDirectory()) {
      await processDir(fullPath, progressCallback, baseInput, baseOutput);
    } else if (/\.(tif)$/i.test(file)) {
      // Ignora .tif
    } else if (/\.(jpg|jpeg|png)$/i.test(file)) {
      const output = path.join(currentOutputDir, path.basename(fullPath).replace(/\.\w+$/, '.webp'));
      await sharp(fullPath)
        .withMetadata()
        .webp({ quality: 75 })
        .toFile(output);
      current++;
      progressCallback({ current, total });
    } else if (/\.xml$/i.test(file)) {
      const output = path.join(currentOutputDir, path.basename(fullPath));
      fs.copyFileSync(fullPath, output);
    }
  }
}
