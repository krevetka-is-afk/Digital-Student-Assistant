import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "https://dsa.s3rg.ru";

export const options = {
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<1000", "p(99)<2000"],
  },
  scenarios: {
    read_heavy: {
      executor: "ramping-arrival-rate",
      startRate: Number(__ENV.START_RATE || 2),
      timeUnit: "1s",
      preAllocatedVUs: Number(__ENV.PRE_ALLOCATED_VUS || 20),
      maxVUs: Number(__ENV.MAX_VUS || 100),
      stages: [
        { target: Number(__ENV.STAGE1_TARGET || 5), duration: __ENV.STAGE1_DURATION || "5m" },
        { target: Number(__ENV.STAGE2_TARGET || 10), duration: __ENV.STAGE2_DURATION || "15m" },
        { target: Number(__ENV.STAGE3_TARGET || 20), duration: __ENV.STAGE3_DURATION || "15m" },
        { target: 0, duration: __ENV.STAGE4_DURATION || "3m" },
      ],
    },
  },
};

export default function () {
  const roll = Math.random();

  let response;
  if (roll < 0.6) {
    response = http.get(`${BASE_URL}/projects/`);
    check(response, { "projects page 200": (r) => r.status === 200 });
  } else if (roll < 0.8) {
    response = http.get(`${BASE_URL}/api/v1/projects/?limit=20`);
    check(response, { "projects api 200": (r) => r.status === 200 });
  } else if (roll < 0.9) {
    response = http.get(`${BASE_URL}/api/v1/recs/search/?q=python`);
    check(response, { "recs search 200": (r) => r.status === 200 });
  } else {
    response = http.get(`${BASE_URL}/health/`);
    check(response, { "health 200": (r) => r.status === 200 });
  }

  sleep(Number(__ENV.SLEEP_SECONDS || 1));
}
