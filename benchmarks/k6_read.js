import http from 'k6/http';
import { sleep } from 'k6';

export let options = {
    stages: [
        { duration: '30s', target: 20 },
        { duration: '2m', target: 200 },
        { duration: '30s', target: 0 },
    ],
};

export default function () {
    http.get('http://127.0.0.1:8000/orderbook');
    http.get('http://127.0.0.1:8000/leaderboard');
    sleep(1);
}
