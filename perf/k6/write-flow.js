import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "https://dsa.s3rg.ru";
const WRITE_USERNAME = __ENV.WRITE_USERNAME;
const WRITE_PASSWORD = __ENV.WRITE_PASSWORD;

if (!WRITE_USERNAME || !WRITE_PASSWORD) {
  throw new Error("WRITE_USERNAME and WRITE_PASSWORD are required");
}

export const options = {
  thresholds: {
    http_req_failed: ["rate<0.02"],
    http_req_duration: ["p(95)<1500", "p(99)<2500"],
  },
  scenarios: {
    write_flow: {
      executor: "ramping-arrival-rate",
      startRate: Number(__ENV.START_RATE || 1),
      timeUnit: "1s",
      preAllocatedVUs: Number(__ENV.PRE_ALLOCATED_VUS || 5),
      maxVUs: Number(__ENV.MAX_VUS || 20),
      stages: [
        { target: Number(__ENV.STAGE1_TARGET || 1), duration: __ENV.STAGE1_DURATION || "5m" },
        { target: Number(__ENV.STAGE2_TARGET || 2), duration: __ENV.STAGE2_DURATION || "10m" },
        { target: Number(__ENV.STAGE3_TARGET || 4), duration: __ENV.STAGE3_DURATION || "10m" },
        { target: 0, duration: __ENV.STAGE4_DURATION || "3m" },
      ],
    },
  },
};

function login() {
  const response = http.post(
    `${BASE_URL}/api/v1/auth/token/`,
    { username: WRITE_USERNAME, password: WRITE_PASSWORD },
    { headers: { Accept: "application/json" } },
  );

  check(response, { "write token issued": (r) => r.status === 200 && !!r.json("token") });
  return response.json("token");
}

function isoDateWithOffset(days) {
  const value = new Date();
  value.setUTCDate(value.getUTCDate() + days);
  return value.toISOString().slice(0, 10);
}

export default function () {
  const token = login();
  const headers = {
    Authorization: `Bearer ${token}`,
    Accept: "application/json",
    "Content-Type": "application/json",
  };

  const slug = `loadtest-${__ENV.RUN_ID || "local"}-${__VU}-${__ITER}-${Date.now()}`;
  const payload = JSON.stringify({
    title: slug,
    description: "Synthetic load-test project created by k6.",
    source_type: "initiative",
    team_size: 2,
    application_opened_at: isoDateWithOffset(-1),
    application_deadline: isoDateWithOffset(7),
    tech_tags: ["python", "loadtest"],
  });

  const create = http.post(`${BASE_URL}/api/v1/projects/`, payload, { headers });
  check(create, { "project created": (r) => r.status === 201 });

  const pk = create.status === 201 ? create.json("pk") : null;
  if (!pk) {
    sleep(Number(__ENV.SLEEP_SECONDS || 1));
    return;
  }

  const submit = http.post(
    `${BASE_URL}/api/v1/projects/${pk}/actions/submit/`,
    null,
    { headers },
  );
  check(submit, {
    "project submitted": (r) => r.status === 200 || r.status === 400,
  });

  sleep(Number(__ENV.SLEEP_SECONDS || 1));
}
