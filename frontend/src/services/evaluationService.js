import { request } from './api';

/** Aggregated analysis. Optional group_id restricts to one sweep group. */
export function getAnalysis(groupId) {
  const q = groupId ? `?group_id=${encodeURIComponent(groupId)}` : '';
  return request(`/api/analysis${q}`);
}
