#!/usr/bin/env node
// Test script for resource-manager.js
import { calculateOptimalWorkers, getSystemResources, checkResourceAvailability } from './resource-manager.js';

console.log('=== Testing Resource Manager ===\n');

// Test 1: Get system resources
console.log('1. Current System Resources:');
const resources = getSystemResources();
console.log(`   CPU: ${resources.cpuCount} cores (${resources.cpuModel})`);
console.log(`   Total RAM: ${resources.totalMemoryGB}GB`);
console.log(`   Free RAM: ${resources.freeMemoryGB}GB`);
console.log(`   Used RAM: ${resources.usedMemoryGB}GB (${resources.memoryUsagePercent}%)`);
console.log(`   Platform: ${resources.platform} ${resources.arch}\n`);

// Test 2: Calculate optimal workers for different scenarios
console.log('2. Optimal Worker Calculations:\n');

const scenarios = [
  { taskType: 'image', avgFileSizeMB: 10, desc: 'Small images (10MB)' },
  { taskType: 'image', avgFileSizeMB: 50, desc: 'Medium images (50MB)' },
  { taskType: 'image', avgFileSizeMB: 120, desc: 'Large images (120MB)' },
  { taskType: 'video', avgFileSizeMB: 100, desc: 'Small videos (100MB)' },
  { taskType: 'video', avgFileSizeMB: 500, desc: 'Large videos (500MB)' },
  { taskType: 'thumbnail', avgFileSizeMB: 0, desc: 'Thumbnail generation' },
  { taskType: 'light', avgFileSizeMB: 0, desc: 'Light file operations' }
];

scenarios.forEach(scenario => {
  const workers = calculateOptimalWorkers({
    taskType: scenario.taskType,
    avgFileSizeMB: scenario.avgFileSizeMB
  });
  console.log(`   ${scenario.desc}: ${workers} workers`);
});

// Test 3: Check resource availability
console.log('\n3. Resource Availability Checks:\n');

const checks = [
  { taskType: 'image', workerCount: 2, desc: '2 image workers' },
  { taskType: 'image', workerCount: 8, desc: '8 image workers' },
  { taskType: 'video', workerCount: 2, desc: '2 video workers' },
  { taskType: 'video', workerCount: 10, desc: '10 video workers (stress test)' }
];

checks.forEach(check => {
  const result = checkResourceAvailability(check.taskType, check.workerCount);
  console.log(`   ${check.desc}: ${result.canProceed ? '✓ OK' : '✗ FAIL'} - ${result.reason}`);
});

console.log('\n=== Test Complete ===');
