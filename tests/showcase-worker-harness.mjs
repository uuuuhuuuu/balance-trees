// Run the production Web Worker under Node for integration tests.
import { parentPort } from 'node:worker_threads';
globalThis.self = globalThis;
globalThis.postMessage = message => parentPort.postMessage(message);
await import('../src/balance_trees/showcase/site/dist/large-worker.mjs');
parentPort.on('message', data => globalThis.onmessage({ data }));
