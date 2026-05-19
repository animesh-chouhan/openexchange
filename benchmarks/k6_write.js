import http from 'k6/http';
import { sleep } from 'k6';

export let options = {
    vus: 50,
    duration: '2m',
};

export default function () {
    const url = 'http://127.0.0.1:8000/orders/random';
    const payload = JSON.stringify({ num_orders: 200, delay: 0.001 });
    const params = { headers: { 'Content-Type': 'application/json' } };
    http.post(url, payload, params);
    sleep(0.5);
}
