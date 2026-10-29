import assert from "node:assert/strict";
import { test } from "node:test";
import { createLocalizer, DICTIONARIES, languageOf, resolveLanguage } from "../src/localize.ts";

test("every language has the same keys and message shapes as English", () => {
  const english = DICTIONARIES.en as Record<string, unknown>;
  for (const [language, dictionary] of Object.entries(DICTIONARIES)) {
    const messages = dictionary as Record<string, unknown>;
    assert.deepEqual(Object.keys(messages).sort(), Object.keys(english).sort(), language);
    for (const [key, message] of Object.entries(english)) {
      assert.equal(typeof messages[key], typeof message, `${language} ${key}`);
      if (typeof message === "object") {
        assert.ok((messages[key] as Record<string, string>).other, `${language} ${key}`);
      }
    }
  }
});

test("no message uses an em-dash", () => {
  for (const dictionary of Object.values(DICTIONARIES)) {
    assert.doesNotMatch(JSON.stringify(dictionary), /\u2014/);
  }
});

test("picks plural forms with the language rules", () => {
  const en = createLocalizer("en").localize;
  assert.equal(en("card.devices", { count: 0 }), "0 devices");
  assert.equal(en("card.devices", { count: 1 }), "1 device");
  assert.equal(en("card.devices", { count: 23 }), "23 devices");
  const fr = createLocalizer("fr").localize;
  assert.equal(fr("card.devices", { count: 0 }), "0 appareil");
  assert.equal(fr("card.devices", { count: 1 }), "1 appareil");
  assert.equal(fr("card.devices", { count: 2 }), "2 appareils");
  assert.equal(fr("summary.integrations", { count: 3 }), "3 intégrations peuvent configurer");
});

test("fills placeholders and formats numbers in the locale", () => {
  assert.equal(createLocalizer("en").localize("card.select", { name: "WiiM" }), "Select WiiM");
  assert.equal(createLocalizer("en").localize("summary.compared", { count: 1442 }), "Compared with 1,442 Marketplace integrations");
  assert.match(createLocalizer("fr").localize("summary.compared", { count: 1442 }), /^Comparé à 1\s442 intégrations du Marketplace$/);
});

test("falls back to the base language, then English", () => {
  assert.equal(resolveLanguage("fr"), "fr");
  assert.equal(resolveLanguage("fr-CA"), "fr");
  assert.equal(resolveLanguage("FR_be"), "fr");
  assert.equal(resolveLanguage("de"), "en");
  assert.equal(resolveLanguage(undefined), "en");
  assert.equal(createLocalizer("fr-CA").localize("card.ignore"), "Ignorer");
  assert.equal(createLocalizer("fr-CA").locale, "fr-CA");
  assert.equal(createLocalizer("de").locale, "en");
  assert.equal(createLocalizer("pt-BR").localize("card.ignore"), "Ignore");
});

test("reads the language from the user locale first", () => {
  assert.equal(languageOf({ locale: { language: "fr" }, language: "en" }), "fr");
  assert.equal(languageOf({ language: "fr" }), "fr");
  assert.equal(languageOf({}), undefined);
  assert.equal(languageOf(undefined), undefined);
});

test("formats relative times", () => {
  const now = new Date(2026, 9, 29, 12);
  const en = createLocalizer("en");
  assert.equal(en.formatRelative(new Date(2026, 9, 29, 1).toISOString(), now), "today");
  assert.equal(en.formatRelative(new Date(2026, 9, 28, 1).toISOString(), now), "yesterday");
  assert.equal(en.formatRelative(new Date(2026, 9, 20, 1).toISOString(), now), "9 days ago");
  assert.equal(en.formatRelative(new Date(2026, 8, 21, 1).toISOString(), now), "1 month ago");
  assert.equal(en.formatRelative(new Date(2025, 11, 10).toISOString(), now), "11 months ago");
  assert.equal(en.formatRelative(new Date(2025, 10, 5).toISOString(), now), "1 year ago");
  assert.equal(createLocalizer("fr").formatRelative(new Date(2025, 10, 5).toISOString(), now), "il y a 1 an");
  assert.equal(en.formatRelative(new Date(2025, 0, 1).toISOString(), now), "2 years ago");
  assert.equal(en.formatRelative(new Date(2026, 10, 2).toISOString(), now), "today");
  assert.equal(en.formatRelative("not a date", now), null);
  assert.equal(createLocalizer("fr").formatRelative(new Date(2026, 9, 20, 1).toISOString(), now), "il y a 9 jours");
});

test("formats compact numbers and dates", () => {
  const en = createLocalizer("en");
  assert.equal(en.formatCompact(6), "6");
  assert.equal(en.formatCompact(2108), "2.1K");
  assert.equal(en.formatCompact(22265), "22.3K");
  assert.match(createLocalizer("fr").formatCompact(2108), /^2,1\sk$/);
  assert.equal(en.formatDate("2026-10-29T08:50:43+00:00"), "Oct 29, 2026");
  assert.equal(en.formatDate("nope"), null);
  assert.equal(en.formatList(["Bluetooth", "SSDP"]), "Bluetooth and SSDP");
});
