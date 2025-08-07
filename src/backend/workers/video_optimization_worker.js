// File: backend/workers/video_optimization_worker.js
import { optimizeVideo } from './video_worker.js';

async function main() {
  const [,, inputPath, outputPath, optionsJson] = process.argv;
  
  if (!inputPath || !outputPath) {
    console.error('Usage: node video_optimization_worker.js <input> <output> [options]');
    process.exit(1);
  }
  
  try {
    const options = optionsJson ? JSON.parse(optionsJson) : {};
    await optimizeVideo(inputPath, outputPath, options);
    process.exit(0);
  } catch (error) {
    console.error('[video_optimization_worker] Error:', error.message);
    process.exit(1);
  }
}

main();
