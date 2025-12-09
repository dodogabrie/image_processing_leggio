// File: backend/utils/resource-manager.js
import os from 'os';
import Logger from '../Logger.js';

const logger = new Logger();

/**
 * Calculate optimal worker count based on available system resources
 * @param {Object} options - Configuration options
 * @param {string} options.taskType - Type of task: 'image', 'video', 'thumbnail', 'light'
 * @param {number} options.avgFileSizeMB - Average file size in MB (optional)
 * @param {number} options.minWorkers - Minimum workers (default: 1)
 * @param {number} options.maxWorkers - Maximum workers override (optional)
 * @returns {number} Optimal worker count
 */
export function calculateOptimalWorkers(options = {}) {
  const {
    taskType = 'image',
    avgFileSizeMB = 0,
    minWorkers = 1,
    maxWorkers = null
  } = options;

  // Get system resources
  const cpuCount = os.cpus().length;
  const totalMemoryGB = os.totalmem() / (1024 ** 3);
  const freeMemoryGB = os.freemem() / (1024 ** 3);
  const memoryUsagePercent = ((totalMemoryGB - freeMemoryGB) / totalMemoryGB) * 100;

  // Define memory requirements per worker for different task types (in GB)
  const memoryRequirements = {
    video: 2.5,      // Video processing is very memory-intensive
    image: 1.0,      // Image processing (Sharp + large images)
    thumbnail: 0.5,  // Thumbnail generation (smaller memory footprint)
    light: 0.3       // Light tasks (file operations, etc.)
  };

  const memoryPerWorker = memoryRequirements[taskType] || memoryRequirements.image;

  // Adjust memory requirement based on file size if provided
  let adjustedMemoryPerWorker = memoryPerWorker;
  if (avgFileSizeMB > 0) {
    // For very large files (>50MB), increase memory requirement
    if (avgFileSizeMB > 50) {
      adjustedMemoryPerWorker = memoryPerWorker * 1.5;
    } else if (avgFileSizeMB > 100) {
      adjustedMemoryPerWorker = memoryPerWorker * 2;
    }
  }

  // Calculate max workers based on available memory
  // Use 70% of free memory to leave headroom for the system
  const availableMemoryForWorkers = freeMemoryGB * 0.7;
  const memoryBasedWorkers = Math.floor(availableMemoryForWorkers / adjustedMemoryPerWorker);

  // Calculate max workers based on CPU
  // Leave at least 1-2 cores free for the system
  const cpuBasedWorkers = cpuCount > 4 ? cpuCount - 2 : Math.max(1, Math.floor(cpuCount / 2));

  // Take the minimum of memory-based and CPU-based calculations
  let optimalWorkers = Math.min(memoryBasedWorkers, cpuBasedWorkers);

  // Apply constraints
  optimalWorkers = Math.max(minWorkers, optimalWorkers);
  if (maxWorkers !== null) {
    optimalWorkers = Math.min(maxWorkers, optimalWorkers);
  }

  // Special handling: if memory usage is already high (>75%), be more conservative
  if (memoryUsagePercent > 75) {
    optimalWorkers = Math.max(minWorkers, Math.floor(optimalWorkers * 0.6));
    logger.warn(`[resource-manager] High memory usage detected (${memoryUsagePercent.toFixed(1)}%), reducing workers to ${optimalWorkers}`);
  }

  // Log resource allocation decision
  logger.info(`[resource-manager] Task: ${taskType}, CPUs: ${cpuCount}, Total RAM: ${totalMemoryGB.toFixed(1)}GB, Free RAM: ${freeMemoryGB.toFixed(1)}GB`);
  logger.info(`[resource-manager] Memory per worker: ${adjustedMemoryPerWorker.toFixed(2)}GB, Optimal workers: ${optimalWorkers}`);

  return optimalWorkers;
}

/**
 * Get current system resource snapshot
 * @returns {Object} System resource information
 */
export function getSystemResources() {
  const totalMemoryGB = os.totalmem() / (1024 ** 3);
  const freeMemoryGB = os.freemem() / (1024 ** 3);
  const usedMemoryGB = totalMemoryGB - freeMemoryGB;
  const memoryUsagePercent = (usedMemoryGB / totalMemoryGB) * 100;

  return {
    cpuCount: os.cpus().length,
    cpuModel: os.cpus()[0]?.model || 'Unknown',
    totalMemoryGB: parseFloat(totalMemoryGB.toFixed(2)),
    freeMemoryGB: parseFloat(freeMemoryGB.toFixed(2)),
    usedMemoryGB: parseFloat(usedMemoryGB.toFixed(2)),
    memoryUsagePercent: parseFloat(memoryUsagePercent.toFixed(1)),
    platform: os.platform(),
    arch: os.arch()
  };
}

/**
 * Check if system has enough resources for a task
 * @param {string} taskType - Type of task
 * @param {number} workerCount - Number of workers needed
 * @returns {Object} { canProceed: boolean, reason: string }
 */
export function checkResourceAvailability(taskType, workerCount) {
  const resources = getSystemResources();
  const memoryRequirements = {
    video: 2.5,
    image: 1.0,
    thumbnail: 0.5,
    light: 0.3
  };

  const memoryPerWorker = memoryRequirements[taskType] || memoryRequirements.image;
  const requiredMemoryGB = memoryPerWorker * workerCount;

  // Check if we have enough free memory (with 20% safety margin)
  const availableMemoryWithMargin = resources.freeMemoryGB * 0.8;

  if (requiredMemoryGB > availableMemoryWithMargin) {
    return {
      canProceed: false,
      reason: `Insufficient memory. Required: ${requiredMemoryGB.toFixed(1)}GB, Available: ${availableMemoryWithMargin.toFixed(1)}GB`
    };
  }

  // Check if memory usage is critically high
  if (resources.memoryUsagePercent > 90) {
    return {
      canProceed: false,
      reason: `Critical memory usage (${resources.memoryUsagePercent}%). Please close other applications.`
    };
  }

  return {
    canProceed: true,
    reason: 'Resources available'
  };
}

/**
 * Monitor system resources and log warnings if thresholds are exceeded
 */
export function monitorResources() {
  const resources = getSystemResources();

  if (resources.memoryUsagePercent > 85) {
    logger.warn(`[resource-manager] High memory usage: ${resources.memoryUsagePercent}% (${resources.usedMemoryGB}GB / ${resources.totalMemoryGB}GB)`);
  }

  if (resources.freeMemoryGB < 1) {
    logger.error(`[resource-manager] Critical: Very low free memory (${resources.freeMemoryGB}GB remaining)`);
  }

  return resources;
}
