import { isTelegram, setupTelegram, telegramInitData } from "./telegram";

afterEach(() => {
  delete window.Telegram;
});

test("no Telegram outside the app", () => {
  expect(telegramInitData()).toBe("");
  expect(isTelegram()).toBe(false);
  expect(() => setupTelegram()).not.toThrow();
});

test("ready and expand are called", () => {
  const ready = vi.fn();
  const expand = vi.fn();
  window.Telegram = { WebApp: { initData: "a=b", ready, expand, colorScheme: "dark" } };
  setupTelegram();
  expect(ready).toHaveBeenCalled();
  expect(expand).toHaveBeenCalled();
  expect(isTelegram()).toBe(true);
  expect(document.documentElement.dataset.scheme).toBe("dark");
});
