import { href, parseRoute } from "./router";

test("parse and build routes", () => {
  expect(parseRoute("")).toEqual({ name: "home" });
  expect(parseRoute("#/new")).toEqual({ name: "new" });
  expect(parseRoute("#/session/ses_1")).toEqual({ name: "session", id: "ses_1" });
  expect(parseRoute("#/session/")).toEqual({ name: "home" });
  expect(parseRoute("#/unknown")).toEqual({ name: "home" });
  expect(href({ name: "session", id: "a b" })).toBe("#/session/a%20b");
  expect(href({ name: "service" })).toBe("#/service");
});
