import { AlertTriangle, Pencil, Search, Trash2, X } from 'lucide-react';
import { useMemo } from 'react';
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { MOOD_LABELS } from '../../constants/tracker';
import { formatDateTime } from '../../utils/date';
import { formatChartDate } from '../../utils/labels';
import MoodIcon from '../MoodIcon';

function JournalSection({
  journalFormData,
  setJournalFormData,
  handleJournalSubmit,
  journals,
  deleteJournal,
  journalSearch,
  setJournalSearch,
  moodTrend
}) {
  const isEditing = Boolean(journalFormData.id);

  const moodChartData = useMemo(
    () => (moodTrend || []).slice(-60).map((point) => ({ ...point, label: formatChartDate(point.date) })),
    [moodTrend]
  );

  return (
    <>
      <div className="mb-8 w-full rounded-3xl border border-gray-100 bg-white p-5 shadow-sm transition-all focus-within:border-gray-300">
        <form onSubmit={handleJournalSubmit}>
          <label htmlFor="journal-content" className="sr-only">
            Запис щоденника
          </label>
          <textarea
            id="journal-content"
            required
            maxLength={10000}
            value={journalFormData.content}
            onChange={(event) => setJournalFormData({ ...journalFormData, content: event.target.value })}
            className="w-full resize-none bg-transparent text-base text-stone-800 outline-none placeholder:text-gray-400"
            rows="2"
            placeholder={isEditing ? 'Редагуйте запис…' : 'Напишіть запис у щоденник…'}
          />

          <div className="mt-3 flex items-center justify-between border-t border-gray-50 pt-3">
            <fieldset className="flex gap-1.5">
              <legend className="sr-only">Настрій</legend>
              {[1, 2, 3, 4, 5].map((mood) => (
                <button
                  key={mood}
                  type="button"
                  onClick={() => setJournalFormData({ ...journalFormData, mood })}
                  aria-pressed={journalFormData.mood === mood}
                  aria-label={MOOD_LABELS[mood]}
                  title={MOOD_LABELS[mood]}
                  className={`flex h-8 w-8 items-center justify-center rounded-full transition-all ${
                    journalFormData.mood === mood
                      ? 'bg-stone-900 text-white'
                      : 'bg-transparent text-gray-400 hover:bg-stone-100'
                  }`}
                >
                  <MoodIcon moodValue={mood} size={16} />
                </button>
              ))}
            </fieldset>

            <div className="flex items-center gap-2">
              {isEditing && (
                <button
                  type="button"
                  onClick={() => setJournalFormData({ id: null, content: '', mood: 3 })}
                  className="px-2 text-sm text-gray-400 hover:text-stone-600"
                >
                  Скасувати
                </button>
              )}
              <button
                type="submit"
                disabled={!journalFormData.content.trim()}
                className="rounded-xl bg-stone-900 px-5 py-1.5 text-sm font-medium text-white transition-colors hover:bg-stone-800 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {isEditing ? 'Оновити' : 'Додати'}
              </button>
            </div>
          </div>
        </form>
      </div>

      {moodChartData.length > 2 && (
        <div className="mb-8 w-full rounded-3xl border border-gray-100 bg-white p-5 shadow-sm md:p-6">
          <div className="mb-4 flex flex-col gap-1 md:flex-row md:items-center md:justify-between">
            <h2 className="text-sm font-semibold text-stone-700">Настрій з часом</h2>
            <p className="text-xs text-gray-400">Середній настрій за дні із записами</p>
          </div>
          <div className="h-40 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={moodChartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="label" minTickGap={30} tick={{ fontSize: 11, fill: '#9ca3af' }} />
                <YAxis domain={[1, 5]} ticks={[1, 2, 3, 4, 5]} tick={{ fontSize: 11, fill: '#9ca3af' }} />
                <Tooltip formatter={(value) => [value, 'Середній настрій']} />
                <Line type="monotone" dataKey="average" stroke="#111827" strokeWidth={2} dot={{ r: 2 }} name="Настрій" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      <div className="w-full space-y-3 pb-12">
        <div className="mb-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-400">
            Щоденник {journals.length > 0 && <span className="ml-1 normal-case text-gray-300">({journals.length})</span>}
          </h2>

          {/* A journal you cannot search stops being useful past a few dozen
              entries, which is exactly when it starts mattering. */}
          <div className="relative w-full sm:w-64">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <label htmlFor="journal-search" className="sr-only">
              Пошук у щоденнику
            </label>
            <input
              id="journal-search"
              type="search"
              value={journalSearch}
              onChange={(event) => setJournalSearch(event.target.value)}
              placeholder="Пошук записів…"
              className="w-full rounded-xl border border-gray-200 bg-white py-2 pl-9 pr-8 text-sm outline-none focus:border-stone-400"
            />
            {journalSearch && (
              <button
                type="button"
                onClick={() => setJournalSearch('')}
                className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-gray-400 hover:text-stone-700"
                aria-label="Очистити пошук"
              >
                <X size={13} />
              </button>
            )}
          </div>
        </div>

        {journals.length === 0 ? (
          <div className="py-12 text-center">
            <p className="text-sm text-gray-400">
              {journalSearch ? `Записів за запитом «${journalSearch}» не знайдено.` : 'Записів у щоденнику ще немає.'}
            </p>
          </div>
        ) : (
          journals.map((journal) => (
            <article
              key={journal.id}
              className={`group rounded-3xl border bg-white p-5 ${
                journal.is_relapse ? 'border-rose-200 bg-rose-50/40' : 'border-gray-100'
              }`}
            >
              <div className="mb-2 flex items-start justify-between gap-3">
                <div className="flex flex-wrap items-center gap-3 text-gray-500">
                  <span className="text-stone-400" title={MOOD_LABELS[journal.mood || 3]}>
                    <MoodIcon moodValue={journal.mood || 3} size={16} />
                  </span>
                  <span className="text-xs font-medium">{formatDateTime(journal.timestamp)}</span>
                  {journal.is_relapse && (
                    <span className="inline-flex items-center gap-1 rounded-md bg-rose-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-rose-700">
                      <AlertTriangle size={10} /> Зрив
                    </span>
                  )}
                </div>

                <div className="flex gap-2 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
                  {/* Relapse entries anchor streak maths, so they are not
                      editable — only removable if logged by mistake. */}
                  {!journal.is_relapse && (
                    <button
                      onClick={() => setJournalFormData(journal)}
                      className="text-gray-400 hover:text-stone-600"
                      aria-label="Редагувати цей запис"
                    >
                      <Pencil size={14} />
                    </button>
                  )}
                  <button
                    onClick={() => deleteJournal(journal.id)}
                    className="text-gray-400 hover:text-rose-500"
                    aria-label="Видалити цей запис"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-stone-700">{journal.content}</p>
            </article>
          ))
        )}
      </div>
    </>
  );
}

export default JournalSection;
