import type { LedgerEvent } from '../types';

export interface CustomerBalanceInfo {
  balance: number; // Integer PKR: positive = customer owes shopkeeper
  lastTxnAt: string | null;
  txnCount: number;
}

export interface DaySummary {
  cashSales: number; // Integer PKR
  udhaarSales: number; // Integer PKR
  paymentsReceived: number; // Integer PKR
  netCreditChange: number; // Integer PKR
  txnCount: number;
}

export function foldCustomerBalance(events: LedgerEvent[], customerId: string): CustomerBalanceInfo {
  let balance = 0;
  let lastTxnAt: string | null = null;
  let txnCount = 0;

  for (const e of events) {
    let affected = false;

    if (e.type === 'sale_udhaar' && e.customer_id === customerId) {
      balance += Math.round(e.amount);
      affected = true;
    } else if (e.type === 'payment_received' && e.customer_id === customerId) {
      balance -= Math.round(Math.abs(e.amount));
      affected = true;
    } else if (e.type === 'adjustment' && e.customer_id === customerId) {
      balance += Math.round(e.amount);
      affected = true;
    } else if (e.type === 'reassign') {
      if (e.customer_id === customerId) {
        balance += Math.round(e.amount);
        affected = true;
      }
      if (e.payload?.previous_customer_id === customerId) {
        balance -= Math.round(e.amount);
        affected = true;
      }
    }

    if (affected) {
      txnCount++;
      if (!lastTxnAt || e.created_at > lastTxnAt) {
        lastTxnAt = e.created_at;
      }
    }
  }

  return {
    balance: Math.round(balance),
    lastTxnAt,
    txnCount,
  };
}

export function foldAllCustomerBalances(events: LedgerEvent[]): Map<string, CustomerBalanceInfo> {
  const map = new Map<string, CustomerBalanceInfo>();
  const customerIds = new Set<string>();

  for (const e of events) {
    if (e.customer_id) customerIds.add(e.customer_id);
    if (e.payload?.previous_customer_id && typeof e.payload.previous_customer_id === 'string') {
      customerIds.add(e.payload.previous_customer_id);
    }
  }

  for (const cid of customerIds) {
    map.set(cid, foldCustomerBalance(events, cid));
  }

  return map;
}

export function foldDaySummary(events: LedgerEvent[], datePrefix?: string): DaySummary {
  const targetPrefix = datePrefix ?? new Date().toISOString().slice(0, 10);
  let cashSales = 0;
  let udhaarSales = 0;
  let paymentsReceived = 0;
  let txnCount = 0;

  for (const e of events) {
    if (e.created_at.startsWith(targetPrefix)) {
      txnCount++;
      if (e.type === 'sale_cash') {
        cashSales += Math.round(e.amount);
      } else if (e.type === 'sale_udhaar') {
        udhaarSales += Math.round(e.amount);
      } else if (e.type === 'payment_received') {
        paymentsReceived += Math.round(Math.abs(e.amount));
      } else if (e.type === 'adjustment') {
        if (e.amount > 0) udhaarSales += Math.round(e.amount);
        else paymentsReceived += Math.round(Math.abs(e.amount));
      }
    }
  }

  return {
    cashSales,
    udhaarSales,
    paymentsReceived,
    netCreditChange: udhaarSales - paymentsReceived,
    txnCount,
  };
}
