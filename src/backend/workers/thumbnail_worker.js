import sharp from 'sharp';
import path from 'path';

async function main() {
  const [,, input, output, aliasOptions] = process.argv;
  if (!input || !output || !aliasOptions) {
    console.error('Usage: node thumbnail_worker.js <input> <output> <aliasOptions>');
    process.exit(1);
  }
  const opts = JSON.parse(aliasOptions);
  try {
    // Usa sempre fit: 'inside' per evitare crop
    // autoOrient: vedi webp_worker.js, senza questo le foto verticali escono coricate.
    let img = sharp(input, { autoOrient: true }).resize(opts.size[0], opts.size[1], { fit: 'inside' });
    img = img.toFormat(opts.format, { quality: opts.quality });
    await img.toFile(output);
    process.exit(0);
  } catch (err) {
    console.error('Thumbnail error:', err.message);
    process.exit(2);
  }
}

main();
