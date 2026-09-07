/**
 * Hardcoded ParsedDraft fixtures for offline development.
 *
 * Eight cases as specified in Phase 1 deliverables (docs/03-build-plan.md):
 *   1. High confidence canonical
 *   2. Medium confidence with a V3 warning
 *   3. Blocking ambiguous customer
 *   4. Blocking missing price
 *   5. name_last
 *   6. name_medial
 *   7. no_name_cash
 *   8. Multi-token SKU
 */

import type { ParsedDraft } from './types';

// --- 1. High confidence canonical ---
export const FIXTURE_HIGH_CONF_CANONICAL: ParsedDraft = {
  draft_id: 'fix-001',
  job_ids: ['job-001'],
  shop_id: 'demo_shop_01',
  customer: {
    customer_id: 'CUST_001',
    raw_name: 'احمد',
    status: 'resolved',
    confidence: 0.95,
    candidates: [],
    source: 'spoken',
  },
  items: [
    {
      sku_id: 'SKU_001',
      raw_name: 'چینی',
      display_name: 'چینی',
      qty: 2.0,
      unit: 'kg',
      spoken_amount: null,
      unit_price: 180,            // int PKR -- AGENTS.md rule 1
      line_total: 360,            // int PKR
      price_source: 'catalogue',
      match_score: 0.96,
      match_status: 'resolved',
      candidates: [],
      derived_fields: ['line_total'],
      token_span: [3, 6],
    },
    {
      sku_id: 'SKU_006',
      raw_name: 'بیسن',
      display_name: 'بیسن',
      qty: 0.5,
      unit: 'kg',
      spoken_amount: null,
      unit_price: 280,
      line_total: 140,
      price_source: 'catalogue',
      match_score: 0.97,
      match_status: 'resolved',
      candidates: [],
      derived_fields: ['line_total'],
      token_span: [6, 9],
    },
  ],
  stated_total: null,
  computed_total: 500,            // int PKR
  payment_type: 'udhaar',
  order_form: 'canonical',
  confidence: 0.91,
  path: 'fast',
  validation: {
    passed: true,
    blocking: [],
    warnings: [],
    requires_llm: false,
  },
};

// --- 2. Medium confidence with a V3 warning ---
export const FIXTURE_V3_WARNING: ParsedDraft = {
  draft_id: 'fix-002',
  job_ids: ['job-002'],
  shop_id: 'demo_shop_01',
  customer: {
    customer_id: 'CUST_004',
    raw_name: 'بلال',
    status: 'resolved',
    confidence: 0.88,
    candidates: [],
    source: 'spoken',
  },
  items: [
    {
      sku_id: 'SKU_003',
      raw_name: 'چاول',
      display_name: 'چاول',
      qty: 5.0,
      unit: 'kg',
      spoken_amount: 5000,        // int PKR — suspiciously high, triggers V3
      unit_price: null,
      line_total: 5000,
      price_source: 'spoken',
      match_score: 0.95,
      match_status: 'resolved',
      candidates: [],
      derived_fields: [],
      token_span: [3, 6],
    },
  ],
  stated_total: null,
  computed_total: 5000,
  payment_type: 'udhaar',
  order_form: 'canonical',
  confidence: 0.72,
  path: 'fast',
  validation: {
    passed: true,
    blocking: [],
    warnings: [
      {
        rule: 'V3',
        item_index: 0,
        message: 'line_total 5000 is outside [0.6×, 1.7×] of median × qty (expected ~1750)',
      },
    ],
    requires_llm: false,
  },
};

// --- 3. Blocking ambiguous customer ---
export const FIXTURE_AMBIGUOUS_CUSTOMER: ParsedDraft = {
  draft_id: 'fix-003',
  job_ids: ['job-003'],
  shop_id: 'demo_shop_01',
  customer: {
    customer_id: null,
    raw_name: 'احمد',
    status: 'ambiguous',          // AGENTS.md rule 9: ambiguous is always blocking
    confidence: 0.45,
    candidates: ['CUST_001', 'CUST_003'],
    source: 'spoken',
  },
  items: [
    {
      sku_id: 'SKU_001',
      raw_name: 'چینی',
      display_name: 'چینی',
      qty: 1.0,
      unit: 'kg',
      spoken_amount: null,
      unit_price: 180,
      line_total: 180,
      price_source: 'catalogue',
      match_score: 0.94,
      match_status: 'resolved',
      candidates: [],
      derived_fields: ['line_total'],
      token_span: [3, 5],
    },
  ],
  stated_total: null,
  computed_total: 180,
  payment_type: 'udhaar',
  order_form: 'canonical',
  confidence: 0.38,
  path: 'fast',
  validation: {
    passed: false,
    blocking: [
      {
        rule: 'V6',
        item_index: null,
        message: 'Customer identity is ambiguous: احمد matches CUST_001 and CUST_003',
      },
    ],
    warnings: [],
    requires_llm: false,          // V6 needs a human, not a model
  },
};

// --- 4. Blocking missing price ---
export const FIXTURE_MISSING_PRICE: ParsedDraft = {
  draft_id: 'fix-004',
  job_ids: ['job-004'],
  shop_id: 'demo_shop_01',
  customer: {
    customer_id: 'CUST_005',
    raw_name: 'عمران',
    status: 'resolved',
    confidence: 0.92,
    candidates: [],
    source: 'spoken',
  },
  items: [
    {
      sku_id: null,
      raw_name: 'نامعلوم',
      display_name: null,
      qty: 2.0,
      unit: 'kg',
      spoken_amount: null,
      unit_price: null,
      line_total: null,           // no price at all -- triggers V7
      price_source: 'missing',
      match_score: 0.0,
      match_status: 'unknown',
      candidates: [],
      derived_fields: [],
      token_span: [3, 5],
    },
  ],
  stated_total: null,
  computed_total: 0,
  payment_type: 'udhaar',
  order_form: 'canonical',
  confidence: 0.25,
  path: 'fast',
  validation: {
    passed: false,
    blocking: [
      {
        rule: 'V7',
        item_index: 0,
        message: 'Line item has price_source "missing" — ask for the amount',
      },
    ],
    warnings: [],
    requires_llm: false,          // V7 needs a human, not a model
  },
};

// --- 5. name_last ---
export const FIXTURE_NAME_LAST: ParsedDraft = {
  draft_id: 'fix-005',
  job_ids: ['job-005'],
  shop_id: 'demo_shop_01',
  customer: {
    customer_id: 'CUST_004',
    raw_name: 'بلال',
    status: 'resolved',
    confidence: 0.90,
    candidates: [],
    source: 'spoken',
  },
  items: [
    {
      sku_id: 'SKU_001',
      raw_name: 'چینی',
      display_name: 'چینی',
      qty: 2.0,
      unit: 'kg',
      spoken_amount: null,
      unit_price: 180,
      line_total: 360,
      price_source: 'catalogue',
      match_score: 0.96,
      match_status: 'resolved',
      candidates: [],
      derived_fields: ['line_total'],
      token_span: [0, 3],
    },
    {
      sku_id: 'SKU_006',
      raw_name: 'بیسن',
      display_name: 'بیسن',
      qty: 0.5,
      unit: 'kg',
      spoken_amount: null,
      unit_price: 280,
      line_total: 140,
      price_source: 'catalogue',
      match_score: 0.97,
      match_status: 'resolved',
      candidates: [],
      derived_fields: ['line_total'],
      token_span: [3, 6],
    },
  ],
  stated_total: null,
  computed_total: 500,
  payment_type: 'udhaar',
  order_form: 'name_last',
  confidence: 0.84,              // 0.91 * 0.92 penalty
  path: 'fast',
  validation: {
    passed: true,
    blocking: [],
    warnings: [],
    requires_llm: false,
  },
};

// --- 6. name_medial ---
export const FIXTURE_NAME_MEDIAL: ParsedDraft = {
  draft_id: 'fix-006',
  job_ids: ['job-006'],
  shop_id: 'demo_shop_01',
  customer: {
    customer_id: 'CUST_005',
    raw_name: 'عمران',
    status: 'resolved',
    confidence: 0.89,
    candidates: [],
    source: 'spoken',
  },
  items: [
    {
      sku_id: 'SKU_002',
      raw_name: 'آٹا',
      display_name: 'آٹا',
      qty: 3.0,
      unit: 'kg',
      spoken_amount: null,
      unit_price: 140,
      line_total: 420,
      price_source: 'catalogue',
      match_score: 0.95,
      match_status: 'resolved',
      candidates: [],
      derived_fields: ['line_total'],
      token_span: [0, 3],
    },
    {
      sku_id: 'SKU_013',
      raw_name: 'تیل',
      display_name: 'تیل',
      qty: 2.0,
      unit: 'l',
      spoken_amount: null,
      unit_price: 550,
      line_total: 1100,
      price_source: 'catalogue',
      match_score: 0.94,
      match_status: 'resolved',
      candidates: [],
      derived_fields: ['line_total'],
      token_span: [6, 9],
    },
  ],
  stated_total: null,
  computed_total: 1520,
  payment_type: 'udhaar',
  order_form: 'name_medial',
  confidence: 0.80,              // penalty for name_medial: * 0.88
  path: 'fast',
  validation: {
    passed: true,
    blocking: [],
    warnings: [],
    requires_llm: false,
  },
};

// --- 7. no_name_cash ---
export const FIXTURE_NO_NAME_CASH: ParsedDraft = {
  draft_id: 'fix-007',
  job_ids: ['job-007'],
  shop_id: 'demo_shop_01',
  customer: {
    customer_id: null,
    raw_name: null,
    status: 'absent',
    confidence: 0.0,
    candidates: [],
    source: 'cash_default',
  },
  items: [
    {
      sku_id: 'SKU_001',
      raw_name: 'چینی',
      display_name: 'چینی',
      qty: 2.0,
      unit: 'kg',
      spoken_amount: null,
      unit_price: 180,
      line_total: 360,
      price_source: 'catalogue',
      match_score: 0.96,
      match_status: 'resolved',
      candidates: [],
      derived_fields: ['line_total'],
      token_span: [0, 3],
    },
    {
      sku_id: 'SKU_006',
      raw_name: 'بیسن',
      display_name: 'بیسن',
      qty: 0.5,
      unit: 'kg',
      spoken_amount: null,
      unit_price: 280,
      line_total: 140,
      price_source: 'catalogue',
      match_score: 0.97,
      match_status: 'resolved',
      candidates: [],
      derived_fields: ['line_total'],
      token_span: [3, 6],
    },
  ],
  stated_total: null,
  computed_total: 500,
  payment_type: 'cash',          // no customer → default cash
  order_form: 'no_name_cash',
  confidence: 0.68,              // lower: * 0.85 penalty for no_name_cash
  path: 'fast',
  validation: {
    passed: true,
    blocking: [],
    warnings: [],
    requires_llm: false,
  },
};

// --- 8. Multi-token SKU ---
export const FIXTURE_MULTI_TOKEN_SKU: ParsedDraft = {
  draft_id: 'fix-008',
  job_ids: ['job-008'],
  shop_id: 'demo_shop_01',
  customer: {
    customer_id: 'CUST_006',
    raw_name: 'فاطمہ',
    status: 'resolved',
    confidence: 0.93,
    candidates: [],
    source: 'spoken',
  },
  items: [
    {
      sku_id: 'SKU_007',
      raw_name: 'لال مرچ',          // multi-token: "laal mirch" is ONE item, not two
      display_name: 'لال مرچ',
      qty: 0.25,
      unit: 'kg',
      spoken_amount: null,
      unit_price: 800,
      line_total: 200,
      price_source: 'catalogue',
      match_score: 0.93,
      match_status: 'resolved',
      candidates: [],
      derived_fields: ['line_total'],
      token_span: [3, 5],          // 2-token span: longest-span-first matching
    },
  ],
  stated_total: null,
  computed_total: 200,
  payment_type: 'udhaar',
  order_form: 'canonical',
  confidence: 0.88,
  path: 'fast',
  validation: {
    passed: true,
    blocking: [],
    warnings: [],
    requires_llm: false,
  },
};

/** All eight fixtures in display order. */
export const ALL_FIXTURES: ParsedDraft[] = [
  FIXTURE_HIGH_CONF_CANONICAL,
  FIXTURE_V3_WARNING,
  FIXTURE_AMBIGUOUS_CUSTOMER,
  FIXTURE_MISSING_PRICE,
  FIXTURE_NAME_LAST,
  FIXTURE_NAME_MEDIAL,
  FIXTURE_NO_NAME_CASH,
  FIXTURE_MULTI_TOKEN_SKU,
];
