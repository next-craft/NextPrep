export const EXAM_CATEGORIES = [
  { value: 'JEE_MAINS', label: 'JEE Mains' },
  { value: 'JEE_ADVANCED', label: 'JEE Advanced' },
  { value: 'NEET_UG', label: 'NEET UG' },
  { value: 'NEET_PG', label: 'NEET PG' },
  { value: 'UPSC_CSE', label: 'UPSC CSE' },
  { value: 'UPSC_OTHER', label: 'UPSC Other' },
  { value: 'CA_FOUNDATION', label: 'CA Foundation' },
  { value: 'CA_INTERMEDIATE', label: 'CA Intermediate' },
  { value: 'CA_FINAL', label: 'CA Final' },
  { value: 'GATE', label: 'GATE' },
  { value: 'GMAT', label: 'GMAT' },
  { value: 'GRE', label: 'GRE' },
  { value: 'IELTS', label: 'IELTS' },
  { value: 'CUET', label: 'CUET' },
  { value: 'CLASS_9', label: 'Class 9' },
  { value: 'CLASS_10', label: 'Class 10' },
  { value: 'CLASS_11', label: 'Class 11' },
  { value: 'CLASS_12', label: 'Class 12' },
  { value: 'OTHER', label: 'Other' },
]

/** value → label lookup for rendering an exam category anywhere in the UI. */
export const EXAM_CATEGORY_LABEL = Object.fromEntries(
  EXAM_CATEGORIES.map((c) => [c.value, c.label])
)

/** Curated subset surfaced as quick links on the landing page. */
export const POPULAR_EXAM_CATEGORIES = [
  'JEE_MAINS',
  'JEE_ADVANCED',
  'NEET_UG',
  'UPSC_CSE',
  'CA_FOUNDATION',
  'GATE',
  'CLASS_12',
  'CUET',
]
