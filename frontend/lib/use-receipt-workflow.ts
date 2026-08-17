"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ReceiptDetail } from "../types/receipt";
import {
  createBrowserVietReceiptApi,
  getApiErrorMessage,
  type VietReceiptApi,
} from "./vietreceipt-api";
import { createReceiptPoller, type ReceiptPoller } from "./receipt-polling";

export interface ReceiptWorkflowState {
  receipt: ReceiptDetail | null;
  initialLoading: boolean;
  polling: boolean;
  error: string | null;
  pollingError: string | null;
}

export function useReceiptWorkflow(
  receiptId: string,
  providedApi?: VietReceiptApi,
) {
  const api = useMemo(
    () => providedApi ?? createBrowserVietReceiptApi(),
    [providedApi],
  );
  const [state, setState] = useState<ReceiptWorkflowState>({
    receipt: null,
    initialLoading: true,
    polling: false,
    error: null,
    pollingError: null,
  });
  const pollerRef = useRef<ReceiptPoller | null>(null);
  const mountedRef = useRef(true);

  const createPollerForReceipt = useCallback(() => {
    pollerRef.current?.stop();
    const poller = createReceiptPoller(
      () => api.getReceipt(receiptId),
      {
        onReceipt: (receipt) => {
          if (!mountedRef.current) return;
          setState((current) => ({
            ...current,
            receipt,
            pollingError: null,
          }));
        },
        onError: (error) => {
          if (!mountedRef.current) return;
          setState((current) => ({
            ...current,
            pollingError: getApiErrorMessage(error),
          }));
        },
        onPollingChange: (polling) => {
          if (!mountedRef.current) return;
          setState((current) => ({ ...current, polling }));
        },
      },
    );
    pollerRef.current = poller;
    return poller;
  }, [api, receiptId]);

  const reload = useCallback(async () => {
    pollerRef.current?.stop();
    setState((current) => ({
      ...current,
      initialLoading: current.receipt === null,
      error: null,
      pollingError: null,
    }));
    try {
      const receipt = await api.getReceipt(receiptId);
      if (!mountedRef.current) return receipt;
      setState((current) => ({
        ...current,
        receipt,
        initialLoading: false,
        error: null,
      }));
      createPollerForReceipt().start(receipt);
      return receipt;
    } catch (error) {
      if (mountedRef.current) {
        setState((current) => ({
          ...current,
          initialLoading: false,
          error: getApiErrorMessage(error),
        }));
      }
      throw error;
    }
  }, [api, createPollerForReceipt, receiptId]);

  useEffect(() => {
    mountedRef.current = true;
    setState({
      receipt: null,
      initialLoading: true,
      polling: false,
      error: null,
      pollingError: null,
    });
    void reload().catch(() => undefined);
    return () => {
      mountedRef.current = false;
      pollerRef.current?.stop();
    };
  }, [reload]);

  const replaceReceipt = useCallback((receipt: ReceiptDetail) => {
    setState((current) => ({ ...current, receipt, error: null }));
  }, []);

  const updateReceipt = useCallback(
    (updater: (receipt: ReceiptDetail) => ReceiptDetail) => {
      setState((current) => ({
        ...current,
        receipt: current.receipt ? updater(current.receipt) : null,
      }));
    },
    [],
  );

  return { ...state, api, reload, replaceReceipt, updateReceipt };
}
