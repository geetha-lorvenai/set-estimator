export type Complexity = "simple" | "moderate" | "complex";

export interface MaterialLine {
  material: string;
  category: string;
  unit: string;
  quantity: number;
  unit_price: number;
  line_total: number;
}

export interface LaborLine {
  role: string;
  workers: number;
  days: number;
  person_days: number;
  daily_rate: number;
  line_total: number;
}

export interface CostSummary {
  material_cost: number;
  complexity: Complexity;
  complexity_surcharge_rate: number;
  complexity_surcharge: number;
  bulk_discount_threshold: number;
  bulk_discount_rate: number;
  bulk_discount_applied: boolean;
  bulk_discount: number;
  adjusted_material_cost: number;
  labor_cost: number;
  total: number;
}

export interface Estimate {
  id: string;
  created_at: string;
  raw_input: string;
  set_name: string | null;
  complexity: Complexity;
  complexity_detected: boolean;
  materials: MaterialLine[];
  labor: LaborLine[];
  material_cost_by_category: Record<string, number>;
  labor_cost_by_role: Record<string, number>;
  summary: CostSummary;
  warnings: string[];
}

export interface EstimateList {
  items: Estimate[];
  total: number;
  limit: number;
  offset: number;
}
