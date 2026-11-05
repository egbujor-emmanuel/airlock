export type Org = "acme" | "payco";

export interface Redaction {
  placeholder: string;
  kind: string;
  category: string;
  via: string;
}

export interface Receipt {
  by: Org;
  hash: string;
  at: number | null;
}

export interface Crossing {
  id: string;
  org: Org;
  status: "proposed" | "approved" | "declined";
  text?: string;
  requested_by?: string;
  redactions?: Redaction[];
  decided_by?: string;
  decided_at?: number;
  proposed_at?: number;
  entry?: string;
  receipt?: Receipt;
  signed: boolean;
  is_query: boolean;
  answers?: string | null;
}

export interface LedgerEntry {
  org: Org;
  type: string;
  seq: number;
  at?: number;
  crossing?: string;
  hash: string;
  linked: boolean;
  signature_ok: boolean;
}

export interface OrgVerification {
  entries: number;
  chain_ok: boolean;
  signatures_ok: boolean;
}

export interface MirrorState {
  source: string;
  orgs: Record<Org, string>;
  missing: Org[];
  verification: Partial<Record<Org, OrgVerification>>;
  crossings: Crossing[];
  entries: LedgerEntry[];
  breaches: LedgerEntry[];
  counts: { ingress: number; redactions: number; blocked: number };
}
