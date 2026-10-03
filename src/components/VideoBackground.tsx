export default function VideoBackground() {
  return (
    <div className="video-bg">
      <video autoPlay muted loop playsInline preload="metadata">
        <source src="/videos/bg.mp4" type="video/mp4" />
      </video>
      <div className="video-overlay" />
    </div>
  );
}