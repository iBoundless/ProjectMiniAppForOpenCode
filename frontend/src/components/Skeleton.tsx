export function Skeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="card" aria-busy="true" data-testid="skeleton">
      {Array.from({ length: lines }, (_, index) => (
        <div key={index} className="skeleton" style={{ width: `${90 - index * 15}%` }} />
      ))}
    </div>
  );
}
