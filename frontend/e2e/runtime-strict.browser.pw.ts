import { expect, test } from "@playwright/test";

const backendPort = Number(process.env.OSTEO_E2E_BACKEND_PORT ?? "18991");

test("E2E backend uses the competition strict runtime", async ({ request }) => {
  const response = await request.get(`http://127.0.0.1:${backendPort}/ready`);

  expect(response.ok()).toBeTruthy();
  const payload = await response.json();
  expect(payload.status).toBe("ok");
  expect(payload.runtime_readiness.runtime_profile).toBe("competition_strict");
  expect(payload.runtime_readiness.strict_startup).toBe(true);
  expect(payload.runtime_readiness.passed).toBe(true);
  expect(payload.runtime_readiness.warning_count).toBe(0);
  expect(payload.inference_config).toContain("osteo_vision_competition_strict.yml");
});
