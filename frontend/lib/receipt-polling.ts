import type { ReceiptDetail } from "../types/receipt";
import { isPollingStatus } from "./receipt-workflow";

export interface ReceiptPollingOptions {
  initialDelayMs?: number;
  maxDelayMs?: number;
  maxAttempts?: number;
  schedule?: (callback: () => void, delayMs: number) => ReturnType<typeof setTimeout>;
  cancel?: (timer: ReturnType<typeof setTimeout>) => void;
  onPollingChange?: (polling: boolean) => void;
  onReceipt: (receipt: ReceiptDetail) => void;
  onError: (error: unknown) => void;
}

export interface ReceiptPoller {
  start(receipt: ReceiptDetail): void;
  stop(): void;
}

export function createReceiptPoller(
  load: () => Promise<ReceiptDetail>,
  options: ReceiptPollingOptions,
): ReceiptPoller {
  const initialDelayMs = options.initialDelayMs ?? 2500;
  const maxDelayMs = options.maxDelayMs ?? 10000;
  const maxAttempts = options.maxAttempts ?? 120;
  const schedule = options.schedule ?? setTimeout;
  const cancel = options.cancel ?? clearTimeout;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let stopped = true;
  let attempts = 0;
  let inFlight = false;

  function stop() {
    stopped = true;
    options.onPollingChange?.(false);
    if (timer !== null) {
      cancel(timer);
      timer = null;
    }
  }

  function queue(delayMs: number) {
    if (stopped || timer !== null || inFlight) return;
    timer = schedule(() => {
      timer = null;
      void tick();
    }, delayMs);
  }

  async function tick() {
    if (stopped || inFlight) return;
    if (attempts >= maxAttempts) {
      stop();
      options.onError(new Error("Polling stopped after reaching the configured attempt limit."));
      return;
    }

    inFlight = true;
    attempts += 1;
    try {
      const receipt = await load();
      options.onReceipt(receipt);
      if (!isPollingStatus(receipt.status)) {
        stop();
        return;
      }
      const delay = Math.min(maxDelayMs, initialDelayMs * 2 ** Math.floor(attempts / 5));
      inFlight = false;
      queue(delay);
    } catch (error) {
      options.onError(error);
      const delay = Math.min(maxDelayMs, initialDelayMs * 2 ** Math.min(3, attempts));
      inFlight = false;
      queue(delay);
    } finally {
      inFlight = false;
    }
  }

  return {
    start(receipt) {
      stop();
      attempts = 0;
      if (!isPollingStatus(receipt.status)) return;
      stopped = false;
      options.onPollingChange?.(true);
      queue(initialDelayMs);
    },
    stop,
  };
}
