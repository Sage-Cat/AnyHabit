import { Check, Copy, Crown, LogIn, LogOut, Pencil, Plus, RefreshCw, Trash2, UserMinus, Users } from 'lucide-react';
import { useState } from 'react';
import { useAppState } from '../../state/appState';
import { formatDate } from '../../utils/date';
import { pluralCount } from '../../utils/plural';
import Modal from '../ui/Modal';

const inputClass =
  'w-full rounded-2xl border border-stone-200 bg-stone-50 px-4 py-3 text-sm outline-none focus:border-stone-400';

function GroupCard({ group, currentUserId }) {
  const { renameGroup, rotateJoinCode, removeGroupMember, leaveGroup, deleteGroup, confirm, notify } = useAppState();

  const [isRenaming, setIsRenaming] = useState(false);
  const [draftName, setDraftName] = useState(group.name);
  const [copied, setCopied] = useState(false);
  const isOwner = group.owner_id === currentUserId;

  const copyJoinCode = async () => {
    try {
      await navigator.clipboard.writeText(group.join_code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard access is denied outside secure contexts; the code is on
      // screen either way, so this is not worth an error toast.
      notify.info(`Код запрошення: ${group.join_code}`);
    }
  };

  const handleRename = async (event) => {
    event.preventDefault();
    if (!draftName.trim() || draftName.trim() === group.name) {
      setIsRenaming(false);
      return;
    }
    try {
      await renameGroup(group.id, draftName.trim());
      notify.success('Групу перейменовано');
      setIsRenaming(false);
    } catch (error) {
      notify.error(error.message || 'Не вдалося перейменувати групу');
    }
  };

  const handleRotate = async () => {
    const accepted = await confirm({
      title: 'Створити новий код запрошення?',
      message: 'Поточний код перестане діяти одразу. Учасників, які вже приєдналися, це не торкнеться.',
      confirmLabel: 'Створити новий код',
      tone: 'default'
    });
    if (!accepted) return;

    try {
      await rotateJoinCode(group.id);
      notify.success('Новий код запрошення створено');
    } catch (error) {
      notify.error(error.message || 'Не вдалося створити новий код');
    }
  };

  const handleRemoveMember = async (member) => {
    const accepted = await confirm({
      title: `Видалити учасника ${member.user.username}?`,
      message:
        'Він втратить доступ до групи та її спільних звичок. Його власні записи й щоденники збережуться.',
      confirmLabel: 'Видалити',
      tone: 'danger'
    });
    if (!accepted) return;

    try {
      await removeGroupMember(group.id, member.user.id);
      notify.success(`Учасника ${member.user.username} видалено`);
    } catch (error) {
      notify.error(error.message || 'Не вдалося видалити учасника');
    }
  };

  const handleLeave = async () => {
    const accepted = await confirm({
      title: `Вийти з групи «${group.name}»?`,
      message: 'Ви втратите доступ до її спільних звичок. Ваша власна історія залишиться з вами.',
      confirmLabel: 'Вийти з групи',
      tone: 'danger'
    });
    if (!accepted) return;

    try {
      await leaveGroup(group.id);
      notify.success(`Ви вийшли з групи «${group.name}»`);
    } catch (error) {
      notify.error(error.message || 'Не вдалося вийти з групи');
    }
  };

  const handleDelete = async () => {
    const accepted = await confirm({
      title: `Видалити групу «${group.name}»?`,
      message: `Спільні звички групи (${group.tracker_count}) стануть особистими звичками тих, хто їх створив. Жодна історія не видаляється.`,
      confirmLabel: 'Видалити групу',
      tone: 'danger',
      requireText: group.name
    });
    if (!accepted) return;

    try {
      await deleteGroup(group.id);
      notify.success('Групу видалено');
    } catch (error) {
      notify.error(error.message || 'Не вдалося видалити групу');
    }
  };

  return (
    <div className="rounded-2xl border border-stone-200 bg-stone-50 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          {isRenaming ? (
            <form onSubmit={handleRename} className="flex gap-2">
              <input
                type="text"
                value={draftName}
                maxLength={80}
                onChange={(event) => setDraftName(event.target.value)}
                className="min-w-0 flex-1 rounded-lg border border-stone-300 bg-white px-3 py-1.5 text-sm outline-none focus:border-stone-500"
                aria-label="Назва групи"
              />
              <button type="submit" className="rounded-lg bg-stone-900 px-3 py-1.5 text-xs font-medium text-white">
                Зберегти
              </button>
              <button
                type="button"
                onClick={() => {
                  setDraftName(group.name);
                  setIsRenaming(false);
                }}
                className="rounded-lg px-2 py-1.5 text-xs text-stone-500"
              >
                Скасувати
              </button>
            </form>
          ) : (
            <h4 className="flex items-center gap-2 truncate font-semibold text-stone-900">
              {group.name}
              {isOwner && <Crown size={14} className="shrink-0 text-amber-500" aria-label="Ви власник цієї групи" />}
            </h4>
          )}
          <p className="mt-1 text-xs text-stone-500">
            {pluralCount(group.member_count, ['учасник', 'учасники', 'учасників'])} · {pluralCount(group.tracker_count, ['спільна звичка', 'спільні звички', 'спільних звичок'])}
          </p>
        </div>

        <div className="flex shrink-0 gap-1">
          {isOwner && !isRenaming && (
            <button
              type="button"
              onClick={() => setIsRenaming(true)}
              title="Перейменувати групу"
              aria-label={`Перейменувати групу «${group.name}»`}
              className="rounded-lg border border-stone-200 p-2 text-stone-500 transition-colors hover:border-stone-300 hover:bg-white hover:text-stone-900"
            >
              <Pencil size={14} />
            </button>
          )}
          <button
            type="button"
            onClick={copyJoinCode}
            title="Скопіювати код запрошення"
            aria-label={`Скопіювати код запрошення для групи «${group.name}»`}
            className="rounded-lg border border-stone-200 p-2 text-stone-500 transition-colors hover:border-stone-300 hover:bg-white hover:text-stone-900"
          >
            {copied ? <Check size={14} className="text-emerald-600" /> : <Copy size={14} />}
          </button>
        </div>
      </div>

      <div className="mt-3 flex items-center gap-2">
        <code className="flex-1 rounded-xl bg-white px-3 py-2 font-mono text-xs tracking-[0.2em] text-stone-600">
          {group.join_code}
        </code>
        {isOwner && (
          <button
            type="button"
            onClick={handleRotate}
            title="Створити новий код запрошення"
            aria-label="Створити новий код запрошення"
            className="rounded-lg border border-stone-200 p-2 text-stone-500 transition-colors hover:border-stone-300 hover:bg-white hover:text-stone-900"
          >
            <RefreshCw size={14} />
          </button>
        )}
      </div>

      {group.members?.length > 0 && (
        <ul className="mt-3 space-y-1 border-t border-stone-200 pt-3">
          {group.members.map((member) => (
            <li key={member.user.id} className="flex items-center justify-between gap-2 px-1 py-1 text-sm">
              <span className="min-w-0 flex-1 truncate text-stone-700">
                {member.user.username}
                {member.user.id === currentUserId && <span className="ml-1.5 text-xs text-stone-400">(ви)</span>}
                <span className="ml-2 text-xs text-stone-400">приєднався(-лась) {formatDate(member.joined_at)}</span>
              </span>
              {isOwner && member.user.id !== group.owner_id && (
                <button
                  type="button"
                  onClick={() => handleRemoveMember(member)}
                  title={`Видалити учасника ${member.user.username}`}
                  aria-label={`Видалити учасника ${member.user.username} з групи «${group.name}»`}
                  className="shrink-0 rounded-lg p-1.5 text-stone-400 transition-colors hover:bg-rose-50 hover:text-rose-600"
                >
                  <UserMinus size={14} />
                </button>
              )}
            </li>
          ))}
        </ul>
      )}

      <div className="mt-3 flex justify-end border-t border-stone-200 pt-3">
        {isOwner ? (
          <button
            type="button"
            onClick={handleDelete}
            className="inline-flex items-center gap-1.5 text-xs font-medium text-rose-600 transition-colors hover:text-rose-700"
          >
            <Trash2 size={13} /> Видалити групу
          </button>
        ) : (
          <button
            type="button"
            onClick={handleLeave}
            className="inline-flex items-center gap-1.5 text-xs font-medium text-rose-600 transition-colors hover:text-rose-700"
          >
            <LogOut size={13} /> Вийти з групи
          </button>
        )}
      </div>
    </div>
  );
}

function GroupManagementModal() {
  const { isGroupManagementOpen, setIsGroupManagementOpen, groups, createGroup, joinGroup, user, notify } =
    useAppState();

  const [groupName, setGroupName] = useState('');
  const [joinCode, setJoinCode] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [activeTab, setActiveTab] = useState('list');

  if (!isGroupManagementOpen) return null;

  const handleCreate = async (event) => {
    event.preventDefault();
    if (!groupName.trim()) return;

    setIsSubmitting(true);
    try {
      await createGroup(groupName.trim());
      notify.success(`Групу «${groupName.trim()}» створено`);
      setGroupName('');
      setActiveTab('list');
    } catch (error) {
      notify.error(error.message || 'Не вдалося створити групу');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleJoin = async (event) => {
    event.preventDefault();
    if (!joinCode.trim()) return;

    setIsSubmitting(true);
    try {
      const group = await joinGroup(joinCode.trim());
      notify.success(`Ви приєдналися до групи ${group?.name ? `«${group.name}»` : ''}`.trim());
      setJoinCode('');
      setActiveTab('list');
    } catch (error) {
      notify.error(error.message || 'Не вдалося приєднатися до групи');
    } finally {
      setIsSubmitting(false);
    }
  };

  const TABS = [
    { id: 'list', label: 'Ваші групи', badge: groups.length },
    { id: 'create', label: 'Створити' },
    { id: 'join', label: 'Приєднатися' }
  ];

  return (
    <Modal
      isOpen
      onClose={() => setIsGroupManagementOpen(false)}
      title="Групи"
      description="Діліться звичками з родиною чи друзями та порівнюйте прогрес."
      size="xl"
    >
      <div className="mb-6 flex gap-2 border-b border-gray-100">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id)}
            aria-current={activeTab === tab.id ? 'page' : undefined}
            className={`border-b-2 px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === tab.id
                ? 'border-stone-900 text-stone-900'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {tab.label}
            {tab.badge !== undefined && (
              <span className="ml-2 rounded-full bg-stone-100 px-2 py-0.5 text-xs font-medium">{tab.badge}</span>
            )}
          </button>
        ))}
      </div>

      {activeTab === 'list' && (
        <div className="space-y-3">
          {groups.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-stone-200 bg-stone-50 p-8 text-center">
              <Users size={32} className="mx-auto mb-3 text-stone-300" />
              <p className="mb-1 text-sm text-stone-600">Груп ще немає</p>
              <p className="text-xs text-stone-500">Створіть групу або приєднайтеся за кодом, яким з вами поділилися.</p>
            </div>
          ) : (
            groups.map((group) => <GroupCard key={group.id} group={group} currentUserId={user?.id} />)
          )}
        </div>
      )}

      {activeTab === 'create' && (
        <form onSubmit={handleCreate} className="space-y-4">
          <div>
            <label htmlFor="group-name" className="mb-2 block text-xs font-semibold uppercase tracking-wider text-stone-500">
              Назва групи
            </label>
            <input
              id="group-name"
              value={groupName}
              maxLength={80}
              onChange={(event) => setGroupName(event.target.value)}
              placeholder="напр. Родина, Друзі, Команда"
              className={inputClass}
              required
            />
          </div>
          <p className="text-xs text-stone-500">
            Ви отримаєте код запрошення, яким можна поділитися. Лише ви можете додавати спільні звички до своєї групи.
          </p>
          <button
            type="submit"
            disabled={isSubmitting}
            className="inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-stone-900 px-4 py-3 text-sm font-medium text-white transition-colors hover:bg-stone-800 disabled:opacity-60"
          >
            <Plus size={16} /> Створити групу
          </button>
        </form>
      )}

      {activeTab === 'join' && (
        <form onSubmit={handleJoin} className="space-y-4">
          <div>
            <label htmlFor="join-code" className="mb-2 block text-xs font-semibold uppercase tracking-wider text-stone-500">
              Код запрошення
            </label>
            <input
              id="join-code"
              value={joinCode}
              maxLength={32}
              onChange={(event) => setJoinCode(event.target.value.toUpperCase())}
              placeholder="ABCD1234"
              className={`${inputClass} tracking-[0.18em] uppercase`}
              required
            />
          </div>
          <p className="text-xs text-stone-500">Попросіть код у когось із учасників групи.</p>
          <button
            type="submit"
            disabled={isSubmitting}
            className="inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-stone-900 px-4 py-3 text-sm font-medium text-white transition-colors hover:bg-stone-800 disabled:opacity-60"
          >
            <LogIn size={16} /> Приєднатися до групи
          </button>
        </form>
      )}
    </Modal>
  );
}

export default GroupManagementModal;
