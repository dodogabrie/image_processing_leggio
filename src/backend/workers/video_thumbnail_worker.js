// File: backend/workers/video_thumbnail_worker.js
import { generateVideoThumbnail } from './video_worker.js';

async function main() {
  const [,, inputPath, outputPath, optionsJson] = process.argv;
  
  if (!inputPath || !outputPath) {
    console.error('Usage: node video_thumbnail_worker.js <input> <output> [options]');
    process.exit(1);
  }
  
  try {
    const options = optionsJson ? JSON.parse(optionsJson) : {};
    await generateVideoThumbnail(inputPath, outputPath, options);
    process.exit(0);
  } catch (error) {
    console.error('[video_thumbnail_worker] Error:', error.message);
    process.exit(1);
  }
}

main();
