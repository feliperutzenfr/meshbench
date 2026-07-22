import { afterEach, expect, test, vi } from "vitest";
import { pickFile, pickFolder } from "./client.js";

afterEach(() => {
  vi.restoreAllMocks();
});

test("pickFile devolve {unavailable} em 409", async () => {
  global.fetch = vi.fn(async () => new Response(null, { status: 409 }));
  expect(await pickFile()).toEqual({ unavailable: true });
});

test("pickFile devolve {path} em 200", async () => {
  global.fetch = vi.fn(
    async () =>
      new Response(JSON.stringify({ path: "C:/a.stl" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
  );
  expect(await pickFile()).toEqual({ path: "C:/a.stl" });
});

test("pickFolder devolve {path:null} quando cancelado", async () => {
  global.fetch = vi.fn(
    async () =>
      new Response(JSON.stringify({ path: null }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
  );
  expect(await pickFolder()).toEqual({ path: null });
});
