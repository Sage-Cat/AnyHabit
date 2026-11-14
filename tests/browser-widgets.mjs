/**
 * Dashboard widgets and the developer surface, driven through a real browser.
 *
 * Covers what unit tests cannot see: every widget type rendering without
 * crashing, widget settings persisting, and the token/webhook UI round-tripping
 * against the API.
 */
import { chromium } from 'playwright';

const BASE = process.env.ANYHABIT_URL || 'http://127.0.0.1:5173';
const RUN_ID = Date.now().toString(36);

const failures = [];
const consoleErrors = [];

function check(label, ok, detail = '') {
  if (ok) console.log(`  PASS  ${label}`);
  else {
    failures.push(`${label} ${detail}`.trim());
    console.log(`  FAIL  ${label} ${detail}`);
  }
}

const browser = await chromium.launch(
  process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {}
);
const page = await browser.newPage({ viewport: { width: 1500, height: 1000 } });

page.on('console', (msg) => {
  if (msg.type() === 'error') consoleErrors.push(msg.text());
});
page.on('pageerror', (err) => consoleErrors.push(`PAGEERROR: ${err.message}`));

const addWidget = async (label) => {
  await page.locator('.home-page button:has-text("Додати віджет")').click();
  await page.waitForSelector('text=Оберіть, що розмістити на головній');
  await page.getByRole('button', { name: new RegExp(`^${label}`) }).first().click();
  await page.waitForTimeout(500);
};

try {
  console.log('\n[1] Sign in and seed data');
  await page.goto(BASE, { waitUntil: 'networkidle' });
  await page.getByPlaceholder('Email або ім\'я користувача').fill('owner@anyhabit.local');
  await page.getByPlaceholder('••••••••').fill('e2e-password');
  await page.locator('form button[type="submit"]').click();
  await page.waitForSelector('.app-sidebar button:has-text("Налаштування")', { timeout: 10000 });

  await page.locator('.home-page button:has-text("Створити звичку")').click();
  await page.waitForSelector('#tracker-name');
  await page.fill('#tracker-name', `Reading ${RUN_ID}`);
  await page.fill('#tracker-unit', 'Pages');
  await page.locator('fieldset input[aria-label="Кількість"]').fill('20');
  // Default type is Quit (Відмова); switch to Build (Накопичення) so the tracker is loggable.
  await page.getByRole('button', { name: /^Відмова$/ }).first().click();
  await page.getByRole('button', { name: /^Накопичення/ }).click();
  await page.getByRole('button', { name: 'Зберегти', exact: true }).click();
  await page.waitForSelector('text=Звичку створено', { timeout: 10000 });
  check('seed tracker created', true);

  await page.locator('.app-sidebar button:has-text("Головна")').click();
  await page.waitForSelector('text=Додати віджет', { timeout: 10000 });

  // The dashboard is stored server-side, so a previous run's widgets are still
  // there. Start from an empty board or the counts below are meaningless.
  await page.locator('.home-page button:has-text("Очистити головну")').click();
  await page.waitForTimeout(500);
  const clearConfirm = page.getByRole('dialog').getByRole('button', { name: 'Очистити головну' });
  if (await clearConfirm.isVisible().catch(() => false)) {
    await clearConfirm.click();
    await page.waitForTimeout(800);
  }
  check('board cleared before adding widgets', (await page.locator('.home-widget-card').count()) === 0);

  console.log('\n[2] Every widget type renders');
  const widgetLabels = [
    'Підсумки впливу',
    'Огляд звичок',
    'Розподіл за категоріями',
    'Найбільший вплив',
    'Фокус на сьогодні',
    'Активні серії',
    'Звичка в центрі уваги',
    'Швидкий запис',
    'Теплова карта регулярності',
    'Остання активність',
    'Стрічка щоденника',
    'Динаміка настрою',
    'Нотатки',
    'Огляд API',
    'Вбудована сторінка'
  ];

  for (const label of widgetLabels) {
    await addWidget(label);
  }
  await page.waitForTimeout(1500);

  const cards = await page.locator('.home-widget-card').count();
  check('all 15 widgets on the board', cards === widgetLabels.length, `rendered ${cards}`);
  check('no crash overlay', !(await page.locator('text=/Щось пішло не так/i').first().isVisible().catch(() => false)));

  console.log('\n[3] Widgets prompt for the config they need');
  check(
    'spotlight asks for a tracker',
    await page.locator('text=Звичку не обрано').first().isVisible()
  );
  check('quick log asks for trackers', await page.locator('text=Звичок не обрано').first().isVisible());
  check('embed asks for a URL', await page.locator('text=Нічого не вбудовано').first().isVisible());

  console.log('\n[4] Configuring a widget persists');
  const spotlightCard = page.locator('.home-widget-card').filter({ hasText: 'Звичка в центрі уваги' }).first();
  await spotlightCard.getByRole('button', { name: 'Редагувати віджет' }).click();
  await page.waitForSelector('#widget-tracker-picker');
  await page.selectOption('#widget-tracker-picker', { label: new RegExp(`Reading ${RUN_ID}`) }).catch(async () => {
    const options = await page.locator('#widget-tracker-picker option').allTextContents();
    const match = options.find((text) => text.includes(RUN_ID));
    await page.selectOption('#widget-tracker-picker', { label: match });
  });
  await page.keyboard.press('Escape');
  await page.waitForTimeout(1200);

  check(
    'spotlight now shows the tracker',
    await page.locator('.home-widget-card').filter({ hasText: `Reading ${RUN_ID}` }).first().isVisible()
  );

  console.log('\n[5] Quick log from a widget writes a log');
  const logButton = page.locator('.home-widget-card button:has-text("Додати +1")').first();
  check('quick log button rendered', await logButton.isVisible());

  // The grid animates card positions, so give the layout a beat to settle
  // before clicking something 2000px down the board.
  await logButton.scrollIntoViewIfNeeded();
  await page.waitForTimeout(600);
  try {
    await logButton.click({ timeout: 8000 });
  } catch (clickError) {
    console.log('CLICK DETAIL:', clickError.message.split('\n').slice(0, 8).join(' | '));
    throw clickError;
  }
  await page.waitForSelector('text=/Додано запис: Reading/', { timeout: 10000 });
  check('quick log fired and confirmed', true);

  console.log('\n[6] Notes widget saves as you type');
  const notesArea = page.locator('#widget-note');
  await notesArea.click();
  await notesArea.pressSequentially('remember to hydrate', { delay: 10 });
  check(
    'focus stays in the note while typing',
    (await page.evaluate(() => document.activeElement?.id)) === 'widget-note',
    await page.evaluate(() => document.activeElement?.id || 'unknown')
  );
  check('note text captured', (await notesArea.inputValue()) === 'remember to hydrate');

  await page.waitForTimeout(1200);
  await page.reload({ waitUntil: 'networkidle' });
  await page.waitForTimeout(1500);
  check('note survived a reload', (await page.locator('#widget-note').inputValue()) === 'remember to hydrate');

  console.log('\n[7] API explorer builds real snippets');
  const explorer = page.locator('.home-widget-card').filter({ hasText: 'Огляд API' }).first();
  const snippet = await explorer.locator('pre').innerText();
  check('snippet targets this instance', snippet.includes('127.0.0.1:5173'), snippet.slice(0, 80));
  check('snippet includes the auth header', snippet.includes('Authorization: Bearer'), snippet.slice(0, 80));

  await explorer.getByRole('button', { name: 'Python' }).click();
  await page.waitForTimeout(300);
  const pythonSnippet = await explorer.locator('pre').innerText();
  check('language switch works', pythonSnippet.includes('httpx'), pythonSnippet.slice(0, 60));

  console.log('\n[8] Developer settings: tokens');
  await page.locator('.app-sidebar button:has-text("Налаштування")').click();
  await page.waitForSelector('text=Налаштуйте AnyHabit');
  // Scope to the dialog: the page behind it also has developer-flavoured text.
  await page.getByRole('dialog').getByRole('button', { name: 'Для розробників' }).click();
  await page.waitForSelector('#token-name', { timeout: 10000 });

  await page.fill('#token-name', 'Browser test token');
  await page.getByRole('button', { name: /Створити токен/i }).click();
  await page.waitForSelector('text=Скопіюйте зараз', { timeout: 10000 });
  check('token created and revealed once', true);

  const revealed = await page.locator('code').filter({ hasText: 'ahb_' }).first().innerText();
  check('token has the expected prefix', revealed.startsWith('ahb_'), revealed.slice(0, 12));

  await page.getByRole('button', { name: 'Я зберіг(-ла) токен' }).click();
  await page.waitForTimeout(400);
  check('token listed after creation', await page.locator('text=Browser test token').first().isVisible());

  console.log('\n[9] Developer settings: webhooks');
  await page.fill('#webhook-url', 'https://example.invalid/hook');
  await page.fill('#webhook-name', 'Example');
  await page.getByRole('button', { name: /Додати вебхук/i }).click();
  await page.waitForSelector('text=Вебхук створено', { timeout: 10000 });
  check('webhook created', true);
  check('signing secret shown', await page.locator('text=Секрет підпису').first().isVisible());
  check(
    'prometheus snippet rendered',
    (await page.locator('pre').last().innerText()).includes('job_name: anyhabit')
  );

  await page.keyboard.press('Escape');
} catch (error) {
  failures.push(`EXCEPTION: ${error.message}`);
  console.log(`\n  EXCEPTION: ${error.message}`);
  await page.screenshot({ path: new URL('./widget-failure.png', import.meta.url).pathname, fullPage: true });
}

const realErrors = consoleErrors.filter(
  (text) =>
    !text.includes('Failed to load resource') &&
    !text.includes('401') &&
    // The Embed widget deliberately points at a URL that will not resolve.
    !text.toLowerCase().includes('example.invalid')
);
console.log(`\n[10] Console clean? ${realErrors.length} error(s)`);
realErrors.slice(0, 8).forEach((text) => console.log(`      ${text.slice(0, 200)}`));
check('no unexpected console errors', realErrors.length === 0, `${realErrors.length} found`);

await browser.close();

console.log('\n' + '='.repeat(60));
if (failures.length) {
  console.log(`${failures.length} CHECK(S) FAILED:`);
  failures.forEach((f) => console.log(`  - ${f}`));
  process.exit(1);
}
console.log('ALL WIDGET / DEVELOPER UI CHECKS PASSED');
