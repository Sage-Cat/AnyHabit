import { chromium } from 'playwright';

// Browser test for the cultivation UI (/practice, /practice/:habitId).
// Re-runnable: every run creates its own uniquely named habit.
const BASE = process.env.ANYHABIT_URL || 'http://127.0.0.1:5173';
const failures = [];
const consoleErrors = [];

function check(label, ok, detail = '') {
  if (ok) console.log(`  PASS  ${label}`);
  else {
    failures.push(`${label} ${detail}`.trim());
    console.log(`  FAIL  ${label} ${detail}`);
  }
}

const browser = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
const context = await browser.newContext({ viewport: { width: 1400, height: 900 } });
const page = await context.newPage();

page.on('console', (msg) => {
  // Failed resource loads from deliberate 4xx probes are not app errors.
  if (msg.type() === 'error' && !/status of 40[0-9]/.test(msg.text())) consoleErrors.push(msg.text());
});
page.on('pageerror', (err) => consoleErrors.push(`PAGEERROR: ${err.message}`));

const habitName = `Режим сну ${Date.now()}`;
let habitId = null;

try {
  console.log('\n[1] Sign in');
  await page.goto(BASE, { waitUntil: 'networkidle' });
  await page.getByPlaceholder("Email або ім'я користувача").fill('owner@anyhabit.local');
  await page.getByPlaceholder('••••••••').fill('e2e-password');
  await page.locator('form button[type="submit"]').click();
  await page.waitForSelector('text=Головна', { timeout: 10000 });
  check('signed in', true);

  console.log('\n[2] Navigate to the page and create a sleep habit');
  await page.getByRole('button', { name: 'Культивація' }).first().click();
  await page.waitForURL('**/practice');
  await page.waitForSelector('h1:has-text("Культивація")');
  check('sidebar link opens /practice', true);
  check('rank card renders', (await page.locator('[data-testid="rank-name"]').innerText()).trim().length > 0);

  await page.locator('#new-practice-habit').click();
  await page.waitForSelector('#new-habit-form');
  await page.getByLabel('Назва', { exact: true }).fill(habitName);
  await page.getByLabel('Підйом не пізніше').fill('23:59');
  await page.getByLabel('Сон від, год').fill('7');
  await page.getByLabel('Сон до, год').fill('9');
  await page.getByRole('button', { name: 'Створити', exact: true }).click();
  await page.waitForSelector('text=Звичку додано до культивації', { timeout: 10000 });
  const card = page.locator('[data-testid="habit-card"]', { hasText: habitName });
  await card.waitFor({ timeout: 10000 });
  check('new habit shows up among active habits', true);
  check(
    'card shows the requirement',
    (await card.locator('[data-testid="today-requirement"]').innerText()).includes('23:59')
  );
  check('card shows the stage badge', (await card.innerText()).includes('Формування'));
  check(
    'no data yet is reported as such',
    (await card.locator('[data-testid="today-status"]').innerText()).trim() === 'Немає даних'
  );

  console.log('\n[3] Quick sleep entry');
  await card.getByRole('button', { name: 'Внести сон' }).click();
  await page.waitForSelector('#sleep-entry-form');
  const defaultBed = await page.getByLabel('Час засинання').inputValue();
  check('bedtime is prefilled with 23:00 of the previous day', defaultBed.endsWith('T23:00'), defaultBed);
  const wakeValue = await page.getByLabel('Час пробудження').inputValue();
  check('wake time is prefilled on a 5-minute grid', Number(wakeValue.slice(-2)) % 5 === 0, wakeValue);

  // The backend reads these values in the user's configured timezone, so
  // "now" is computed in that zone; 8 hours of sleep ending now is deterministic.
  const { bedValue, wakeValueNow } = await page.evaluate(async () => {
    const overview = await (await fetch('/cultivation/overview', { credentials: 'include' })).json();
    const parts = Object.fromEntries(
      new Intl.DateTimeFormat('en-GB', {
        timeZone: overview.timezone,
        hourCycle: 'h23',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      })
        .formatToParts(new Date())
        .map((p) => [p.type, p.value])
    );
    const wake = new Date(
      Date.UTC(+parts.year, +parts.month - 1, +parts.day, +parts.hour, Math.floor(+parts.minute / 5) * 5)
    );
    const bed = new Date(wake.getTime() - 8 * 3600 * 1000);
    const fmt = (d) => d.toISOString().slice(0, 16);
    return { bedValue: fmt(bed), wakeValueNow: fmt(wake) };
  });
  await page.getByLabel('Час засинання').fill(bedValue);
  await page.getByLabel('Час пробудження').fill(wakeValueNow);
  await page.getByRole('button', { name: 'Записати сон' }).click();
  const toast = page.locator('text=/Сон записано/').first();
  await toast.waitFor({ timeout: 10000 });
  const toastText = (await toast.innerText()).trim();
  check('toast reports the resulting day status', /Сон записано.*:\s*\S+/.test(toastText), toastText);
  const statusLabel = toastText.split(':').pop().trim();

  await page.waitForFunction(
    (name) => {
      const el = [...document.querySelectorAll('[data-testid="habit-card"]')].find((c) => c.textContent.includes(name));
      return el && !el.textContent.includes('Немає даних');
    },
    habitName,
    { timeout: 10000 }
  );
  const pill = (await card.locator('[data-testid="today-status"]').innerText()).trim();
  check('day status appears on /practice', pill === statusLabel && statusLabel.length > 0, `${pill} vs ${statusLabel}`);
  check('good night counts as success', statusLabel === 'Успіх', statusLabel);

  console.log('\n[4] Habit page');
  await card.getByRole('link', { name: habitName }).click();
  await page.waitForURL(/\/practice\/\d+$/);
  habitId = page.url().match(/\/practice\/(\d+)$/)[1];
  await page.waitForSelector('[data-testid="habit-title"]');
  check('habit page shows the title', (await page.locator('[data-testid="habit-title"]').innerText()) === habitName);
  const detailPill = (
    await page.locator('[data-testid="today-block"] [data-testid="today-status"]').innerText()
  ).trim();
  check('day status appears on the habit page', detailPill === statusLabel, detailPill);
  const dayCells = await page.locator('[data-testid="day-calendar"] button').count();
  check('calendar renders day cells', dayCells >= 1, String(dayCells));
  const todayCell = await page.locator('[data-testid="day-calendar"] button').last().getAttribute('aria-label');
  check('calendar marks today with the status', todayCell.endsWith(statusLabel), todayCell);

  const criteria = page.locator('[data-testid="integration-block"] li[data-status]');
  const criteriaCount = await criteria.count();
  check('integration criteria are listed', criteriaCount > 0, String(criteriaCount));
  let unverified = 0;
  let badLook = 0;
  for (let i = 0; i < criteriaCount; i += 1) {
    const item = criteria.nth(i);
    const status = await item.getAttribute('data-status');
    const text = await item.innerText();
    if (status === 'untested' || status === 'manual') {
      unverified += 1;
      if (/виконано/.test(text.replace('не виконано', ''))) badLook += 1;
      if (status === 'untested' && !text.includes('не перевірено')) badLook += 1;
      if (status === 'manual' && !text.includes('оцінюєте ви')) badLook += 1;
    }
    if (status === 'met' && !text.includes('виконано')) badLook += 1;
  }
  check('at least one untested/manual criterion is present', unverified > 0, String(unverified));
  check('untested/manual criteria are never shown as met', badLook === 0, String(badLook));

  check('passport view renders', (await page.locator('[data-testid="passport-view"]').innerText()).includes(habitName));
  check(
    'version history lists the first version',
    (await page.locator('[data-testid="version-history"] li').count()) >= 1
  );

  console.log('\n[5] Manual mark and passport edit');
  await page.getByLabel('Статус позначки').selectOption('exception');
  await page.getByLabel('Дата позначки').fill(bedValue.slice(0, 10));
  await page.getByLabel('Причина позначки').fill('Подорож');
  await page.getByRole('button', { name: 'Зберегти позначку' }).click();
  await page.waitForSelector('text=День позначено', { timeout: 10000 });
  check('manual mark saved', true);

  await page.getByRole('button', { name: 'Редагувати паспорт' }).click();
  await page.getByLabel('Сон до, год', { exact: true }).fill('9.5');
  await page.getByLabel('Причина зміни паспорта').fill('Перевірка');
  await page.getByRole('button', { name: 'Зберегти нову версію' }).click();
  await page.waitForSelector('text=Створено нову версію паспорта', { timeout: 10000 });
  await page.waitForFunction(() => document.querySelectorAll('[data-testid="version-history"] li').length >= 2);
  check('new passport version appears in history', true);

  console.log('\n[6] Direct reload of both routes');
  for (const path of ['/practice', `/practice/${habitId}`]) {
    const response = await page.goto(`${BASE}${path}`, { waitUntil: 'networkidle' });
    const type = response.headers()['content-type'] || '';
    check(`${path} is served as HTML`, type.includes('text/html'), type);
    const selector = path === '/practice' ? 'h1:has-text("Культивація")' : '[data-testid="habit-title"]';
    await page.waitForSelector(selector, { timeout: 10000 });
    const body = (await page.locator('body').innerText()).trim();
    check(`${path} renders the app, not JSON`, !body.startsWith('{') && body.includes('Культивація'));
  }

  console.log('\n[7] Home card and phone width');
  await page.goto(BASE, { waitUntil: 'networkidle' });
  await page.waitForSelector('[data-testid="home-cultivation-card"]', { timeout: 10000 });
  const homeText = await page.locator('[data-testid="home-cultivation-card"]').innerText();
  check(
    'home card shows rank and a sleep entry button',
    homeText.toLowerCase().includes('ранг') && homeText.includes('Внести сон')
  );
  const rankCard = page.locator('[data-testid="home-rank-card"]');
  check('rank has its own card', (await rankCard.innerText()).toLowerCase().includes('ранг культивації'));
  const ladderSteps = await rankCard.locator('ol li [role="img"]').count();
  check('rank card draws an emblem for every rank', ladderSteps >= 2, String(ladderSteps));
  check(
    'rank card does not carry habit actions',
    (await rankCard.getByRole('button', { name: 'Внести сон' }).count()) === 0
  );
  const todayHabit = page.locator('[data-testid="home-today-card"] [data-testid="home-habit"]', { hasText: habitName });
  check('today card lists the active habit', (await todayHabit.count()) === 1);

  const boolName = `Телефон ${Date.now()}`;
  await page.evaluate(async (name) => {
    const response = await fetch('/cultivation/habits', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kind: 'boolean', spec: { name, stage: 'formation' }, reason: 'e2e' })
    });
    if (!response.ok) throw new Error(await response.text());
  }, boolName);
  await page.reload({ waitUntil: 'networkidle' });
  const boolRow = page.locator('[data-testid="home-today-card"] [data-testid="home-habit"]', { hasText: boolName });
  await boolRow.waitFor({ timeout: 10000 });
  await boolRow.getByRole('button', { name: 'Виконано' }).click();
  await page.waitForSelector(`text=«${boolName}» — виконано`, { timeout: 10000 });
  await boolRow.getByRole('button', { name: 'Виконано' }).waitFor({ state: 'detached', timeout: 10000 });
  check(
    'one tap marks a yes/no habit done for today',
    (await boolRow.locator('[data-testid="today-status"]').innerText()).trim() === 'Успіх'
  );

  await page.setViewportSize({ width: 390, height: 800 });
  for (const path of ['/practice', `/practice/${habitId}`]) {
    await page.goto(`${BASE}${path}`, { waitUntil: 'networkidle' });
    await page.waitForSelector('h1');
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    check(`${path} has no horizontal overflow at 390px`, overflow <= 0, String(overflow));
  }

  console.log('\n[8] Stage change, minimum mode, archive');
  await page.setViewportSize({ width: 1400, height: 900 });
  await page.goto(`${BASE}/practice/${habitId}`, { waitUntil: 'networkidle' });
  const header = page.locator('[data-testid="habit-title"]').locator('xpath=..');
  await page.getByLabel('Новий етап').selectOption('stabilization');
  await page.getByLabel('Причина зміни етапу').fill('Перевірка етапу');
  await page.getByRole('button', { name: 'Змінити етап', exact: true }).click();
  await page.waitForSelector('text=Етап змінено', { timeout: 10000 });
  await header.locator('text=Стабілізація').waitFor({ timeout: 10000 });
  check('stage change shows the new stage', true);
  check(
    'stage change is recorded as a passport version',
    (await page.locator('[data-testid="version-history"]').innerText()).includes('Перевірка етапу')
  );

  const modeBlock = page.locator('[data-testid="mode-block"]');
  await page.getByLabel('Причина режиму мінімуму').fill('Хвороба');
  await modeBlock.getByRole('button', { name: 'Увімкнути режим мінімуму' }).click();
  await page.waitForSelector('text=Режим мінімуму увімкнено', { timeout: 10000 });
  await header.locator('text=режим мінімуму').waitFor({ timeout: 10000 });
  check('minimum mode badge appears', true);
  check('active mode shows its reason', (await modeBlock.innerText()).includes('Хвороба'));
  await modeBlock.getByRole('button', { name: 'Завершити режим мінімуму' }).click();
  await page.waitForSelector('text=Режим мінімуму завершено', { timeout: 10000 });
  await modeBlock.getByRole('button', { name: 'Увімкнути режим мінімуму' }).waitFor({ timeout: 10000 });
  // The end date is inclusive, so today itself still counts under the minimum.
  check('minimum mode can be ended', !(await modeBlock.innerText()).includes('Діє з'));

  await page.getByRole('button', { name: 'Архівувати звичку' }).click();
  await page.getByRole('button', { name: 'Архівувати', exact: true }).click();
  await page.waitForURL('**/practice', { timeout: 10000 });
  await page.waitForSelector('text=Звичку архівовано', { timeout: 10000 });
  await page.waitForSelector('[data-testid="rank-name"]');
  check(
    'archived habit leaves the active list',
    (await page.locator('[data-testid="habit-card"]', { hasText: habitName }).count()) === 0
  );
  await page.goto(`${BASE}/practice/${habitId}`, { waitUntil: 'networkidle' });
  await header.locator('text=в архіві').waitFor({ timeout: 10000 });
  check('archived habit page is marked', true);
  check(
    'archived habit hides write actions',
    (await page
      .locator('[data-testid="mark-form"], [data-testid="mode-block"], [data-testid="stage-form"]')
      .count()) === 0
  );
  await page.getByRole('button', { name: 'Повернути з архіву' }).click();
  await page.waitForSelector('text=Звичку повернено з архіву', { timeout: 10000 });
  await page.locator('[data-testid="mark-form"]').waitFor({ timeout: 10000 });
  check('unarchived habit is writable again', (await header.locator('text=в архіві').count()) === 0);

  check('no console errors', consoleErrors.length === 0, consoleErrors.join(' | '));
} catch (error) {
  failures.push(`Unhandled: ${error.message}`);
  console.log(`  FAIL  unhandled: ${error.stack || error.message}`);
} finally {
  await browser.close();
}

console.log(failures.length ? `\n${failures.length} FAILED` : '\nALL PASSED');
process.exit(failures.length ? 1 : 0);
