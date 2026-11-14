import { useState } from 'react';
import { ArrowRight, Loader, LockKeyhole, Mail, UserRound } from 'lucide-react';

const AUTH_COPY = {
  title: 'Приватно за замовчуванням. Спільно — за вашим вибором.',
  subtitle: 'Увійдіть або створіть акаунт, щоб вести особисті звички та спільні звички в групах.',
  note: 'Власний сервер. Ваші дані не покидають його.'
};

function AuthScreen({ onLogin, onRegister, error, isBusy }) {
  const [mode, setMode] = useState('login');
  const [form, setForm] = useState({ username: '', email: '', identifier: '', password: '' });
  const [localError, setLocalError] = useState('');

  const handleSubmit = async (event) => {
    event.preventDefault();
    setLocalError('');
    try {
      if (mode === 'login') {
        await onLogin(form.identifier.trim(), form.password);
      } else {
        await onRegister(form.username.trim(), form.email.trim(), form.password);
      }
    } catch (err) {
      setLocalError(err.message || 'Сталася помилка. Спробуйте ще раз.');
    }
  };

  return (
    <div className="auth-screen min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(233,229,216,0.9),_transparent_32%),linear-gradient(135deg,_#f7f2e7_0%,_#fdfdfb_38%,_#eef2f2_100%)] text-stone-900 flex items-center justify-center px-4 py-10">
      <div className="w-full max-w-5xl grid lg:grid-cols-[1.15fr_0.85fr] gap-6">
        <section className="rounded-[2rem] border border-white/60 bg-white/70 backdrop-blur-xl shadow-[0_24px_80px_rgba(15,23,42,0.10)] p-8 md:p-12 flex flex-col justify-between overflow-hidden relative">
          <div className="absolute inset-0 pointer-events-none bg-[linear-gradient(120deg,rgba(17,24,39,0.02),transparent_40%,rgba(101,67,33,0.04))]" />
          <div className="relative z-10 max-w-xl">
            <p className="text-xs uppercase tracking-[0.34em] text-stone-500 font-semibold">AnyHabit</p>
            <div className="inline-flex items-center gap-3 rounded-full border border-stone-200 bg-white px-4 py-2 text-sm font-medium text-stone-600 shadow-sm">
              <LockKeyhole size={16} />
              Особистий простір
            </div>
            <h1 className="mt-8 text-4xl md:text-6xl font-semibold tracking-tight text-stone-950 leading-[0.95]">
              {AUTH_COPY.title}
            </h1>
            <p className="mt-5 text-lg text-stone-600 max-w-2xl leading-8">{AUTH_COPY.subtitle}</p>
            <div className="mt-10 grid md:grid-cols-3 gap-4 text-sm">
              <div className="rounded-2xl border border-stone-200 bg-stone-50/80 p-4">
                <div className="font-semibold text-stone-900">Спершу приватність</div>
                <p className="mt-2 text-stone-600">Кожен користувач має окремі звички, щоденники та налаштування головної.</p>
              </div>
              <div className="rounded-2xl border border-stone-200 bg-stone-50/80 p-4">
                <div className="font-semibold text-stone-900">Спільні групи</div>
                <p className="mt-2 text-stone-600">Запросіть родину чи друзів і порівнюйте прогрес у груповій звичці.</p>
              </div>
              <div className="rounded-2xl border border-stone-200 bg-stone-50/80 p-4">
                <div className="font-semibold text-stone-900">Дві серії</div>
                <p className="mt-2 text-stone-600">Стежте за власною регулярністю та серією всієї групи поруч.</p>
              </div>
            </div>
          </div>

          <p className="relative z-10 mt-10 text-xs uppercase tracking-[0.24em] text-stone-400">{AUTH_COPY.note}</p>
        </section>

        <section className="rounded-[2rem] border border-stone-200 bg-white shadow-[0_24px_80px_rgba(15,23,42,0.10)] p-6 md:p-8">
          <div className="mb-5 flex items-center gap-3">
            <img src="/AnyHabit.png" alt="AnyHabit" className="w-8 h-8 rounded-lg object-cover" />
            <div>
              <p className="text-xs uppercase tracking-[0.18em] text-stone-400">Ласкаво просимо до</p>
              <p className="text-lg font-semibold text-stone-900">AnyHabit</p>
            </div>
          </div>
          <div className="flex items-center gap-2 rounded-full bg-stone-100 p-1 w-fit mb-6">
            <button
              type="button"
              onClick={() => setMode('login')}
              className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${
                mode === 'login' ? 'bg-white text-stone-900 shadow-sm' : 'text-stone-500'
              }`}
            >
              Увійти
            </button>
            <button
              type="button"
              onClick={() => setMode('register')}
              className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${
                mode === 'register' ? 'bg-white text-stone-900 shadow-sm' : 'text-stone-500'
              }`}
            >
              Створити акаунт
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === 'register' && (
              <label className="block">
                <span className="mb-2 block text-xs font-semibold uppercase tracking-wider text-stone-500">Ім'я користувача</span>
                <div className="relative">
                  <UserRound size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-stone-400" />
                  <input
                    type="text"
                    required
                    value={form.username}
                    onChange={(event) => setForm({ ...form, username: event.target.value })}
                    className="w-full rounded-2xl border border-stone-200 bg-stone-50 pl-11 pr-4 py-3 text-sm outline-none focus:border-stone-400"
                    placeholder="Ваше ім'я"
                  />
                </div>
              </label>
            )}

            <label className="block">
              <span className="mb-2 block text-xs font-semibold uppercase tracking-wider text-stone-500">
                {mode === 'login' ? 'Email або ім\'я користувача' : 'Email'}
              </span>
              <div className="relative">
                <Mail size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-stone-400" />
                <input
                  type={mode === 'login' ? 'text' : 'email'}
                  required
                  value={mode === 'login' ? form.identifier : form.email}
                  onChange={(event) =>
                    setForm(mode === 'login' ? { ...form, identifier: event.target.value } : { ...form, email: event.target.value })
                  }
                  className="w-full rounded-2xl border border-stone-200 bg-stone-50 pl-11 pr-4 py-3 text-sm outline-none focus:border-stone-400"
                  placeholder={mode === 'login' ? 'Email або ім\'я користувача' : 'you@example.com'}
                />
              </div>
            </label>

            <label className="block">
              <span className="mb-2 block text-xs font-semibold uppercase tracking-wider text-stone-500">Пароль</span>
              <div className="relative">
                <LockKeyhole size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-stone-400" />
                <input
                  type="password"
                  required
                  minLength={mode === 'register' ? 8 : undefined}
                  autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
                  value={form.password}
                  onChange={(event) => setForm({ ...form, password: event.target.value })}
                  className="w-full rounded-2xl border border-stone-200 bg-stone-50 pl-11 pr-4 py-3 text-sm outline-none focus:border-stone-400"
                  placeholder="••••••••"
                />
              </div>
              {mode === 'register' && (
                <span className="mt-1.5 block text-[11px] text-stone-400">Щонайменше 8 символів.</span>
              )}
            </label>

            {(error || localError) && (
              <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 animate-in fade-in">
                {error || localError}
              </div>
            )}

            <button
              type="submit"
              disabled={isBusy}
              className="w-full inline-flex items-center justify-center gap-2 rounded-2xl bg-stone-900 px-5 py-3 text-sm font-medium text-white transition-colors hover:bg-stone-800 disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {isBusy && <Loader size={16} className="animate-spin" />}
              {isBusy ? 'Завантаження…' : (mode === 'login' ? 'Увійти' : 'Зареєструватися')}
              {!isBusy && <ArrowRight size={16} />}
            </button>
          </form>
        </section>
      </div>
    </div>
  );
}

export default AuthScreen;
