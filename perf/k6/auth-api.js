import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "https://dsa.s3rg.ru";
const AUTH_USERNAME = __ENV.AUTH_USERNAME;
const AUTH_PASSWORD = __ENV.AUTH_PASSWORD;

if (!AUTH_USERNAME || !AUTH_PASSWORD) {
  throw new Error("AUTH_USERNAME and AUTH_PASSWORD are required");
}

export const options = {
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<1000", "p(99)<2000"],
  },
  scenarios: {
    auth_api: {
      executor: "ramping-arrival-rate",
      startRate: Number(__ENV.START_RATE || 1),
      timeUnit: "1s",
      preAllocatedVUs: Number(__ENV.PRE_ALLOCATED_VUS || 10),
      maxVUs: Number(__ENV.MAX_VUS || 50),
      stages: [
        { target: Number(__ENV.STAGE1_TARGET || 2), duration: __ENV.STAGE1_DURATION || "5m" },
        { target: Number(__ENV.STAGE2_TARGET || 5), duration: __ENV.STAGE2_DURATION || "15m" },
        { target: Number(__ENV.STAGE3_TARGET || 10), duration: __ENV.STAGE3_DURATION || "15m" },
        { target: 0, duration: __ENV.STAGE4_DURATION || "3m" },
      ],
    },
  },
};

function login() {
  const response = http.post(
    `${BASE_URL}/api/v1/auth/token/`,
    { username: AUTH_USERNAME, password: AUTH_PASSWORD },
    { headers: { Accept: "application/json" } },
  );

  check(response, { "token issued": (r) => r.status === 200 && !!r.json("token") });
  return response.json("token");
}

export default function () {
  const token = login();
  const headers = {
    Authorization: `Bearer ${token}`,
    Accept: "application/json",
  };

  const me = http.get(`${BASE_URL}/api/v1/account/me/`, { headers });
  check(me, { "account me 200": (r) => r.status === 200 });

  const projects = http.get(`${BASE_URL}/api/v1/projects/?limit=20`, { headers });
  check(projects, { "projects api 200": (r) => r.status === 200 });

  sleep(Number(__ENV.SLEEP_SECONDS || 1));
}
