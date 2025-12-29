import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  vus: 10, // 10 pemanggil simultan
  duration: '10s',
};

export default function () {
  const url = 'http://localhost:8080/publish';
  const payload = JSON.stringify([{
    topic: 'load-test',
    event_id: `id-${Math.floor(Math.random() * 100)}`, // Simulasi duplikasi (0-99)
    timestamp: new Date().toISOString(),
    source: 'k6-stress-test',
    payload: { data: 'test' }
  }]);

  const params = { headers: { 'Content-Type': 'application/json' } };
  const res = http.post(url, payload, params);
  
  check(res, { 'is status 201': (r) => r.status === 201 });
}