// Coloured faces with distinct expressions, so the mood reads at a glance.
// Colours are inline: they must not follow the dark-theme class overrides.
const FACES = {
  1: { fill: '#fb7185', line: '#be123c', ink: '#4c0519' },
  2: { fill: '#fdba74', line: '#c2410c', ink: '#431407' },
  3: { fill: '#fde047', line: '#a16207', ink: '#422006' },
  4: { fill: '#a3e635', line: '#4d7c0f', ink: '#1a2e05' },
  5: { fill: '#4ade80', line: '#15803d', ink: '#052e16' }
};

function Features({ mood, ink }) {
  const stroke = { stroke: ink, strokeWidth: 2.2, strokeLinecap: 'round', fill: 'none' };
  const eyes = (
    <>
      <circle cx="12.5" cy="15.5" r="2" fill={ink} />
      <circle cx="23.5" cy="15.5" r="2" fill={ink} />
    </>
  );
  switch (mood) {
    case 1:
      return (
        <>
          <path d="M8.5 12.5 L14 10.3 M27.5 12.5 L22 10.3" {...stroke} />
          <circle cx="12.5" cy="16" r="1.8" fill={ink} />
          <circle cx="23.5" cy="16" r="1.8" fill={ink} />
          <path d="M11.6 19.2 q-1.6 2.6 0 3.6 q1.6 -1 0 -3.6 z" fill="#38bdf8" />
          <path d="M11 27 Q18 19.5 25 27" {...stroke} />
        </>
      );
    case 2:
      return (
        <>
          <path d="M9.5 12 L14 11 M26.5 12 L22 11" {...stroke} />
          {eyes}
          <path d="M12 25.5 Q18 21.5 24 25.5" {...stroke} />
        </>
      );
    case 4:
      return (
        <>
          {eyes}
          <path d="M11.5 21.5 Q18 27.5 24.5 21.5" {...stroke} />
        </>
      );
    case 5:
      return (
        <>
          <path d="M10 16 Q12.5 12.3 15 16 M21 16 Q23.5 12.3 26 16" {...stroke} />
          <path d="M10 20 H26 Q26 28.5 18 28.5 Q10 28.5 10 20 Z" fill={ink} />
          <path d="M14 25.6 Q18 23.4 22 25.6 Q20.5 27.4 18 27.4 Q15.5 27.4 14 25.6 Z" fill="#fb7185" />
        </>
      );
    default:
      return (
        <>
          {eyes}
          <path d="M12 24 H24" {...stroke} />
        </>
      );
  }
}

function MoodIcon({ moodValue, size = 20, className = '' }) {
  const mood = FACES[moodValue] ? moodValue : 3;
  const { fill, line, ink } = FACES[mood];
  return (
    <svg width={size} height={size} viewBox="0 0 36 36" className={className} aria-hidden="true">
      <circle cx="18" cy="18" r="16" fill={fill} stroke={line} strokeWidth="1.5" />
      <Features mood={mood} ink={ink} />
    </svg>
  );
}

export default MoodIcon;
