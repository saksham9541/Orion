/**
 * Static login backdrop: the Vande Bharat photo fills the page, toned toward warm grey (#65635E).
 * The glass card sits in the centre. No animation.
 */
export default function LoginScene() {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 z-0 overflow-hidden bg-[#65635E]">
      <img
        src="/login-train.jpg"
        alt=""
        draggable={false}
        className="absolute inset-0 h-full w-full select-none object-cover object-[30%_50%]"
      />
      <div className="absolute inset-0" style={{ background: 'rgba(101,99,94,0.30)' }} />
      <div
        className="absolute inset-0"
        style={{ background: 'linear-gradient(to bottom, rgba(60,58,54,0.5), rgba(60,58,54,0) 38%, rgba(40,38,35,0) 70%, rgba(40,38,35,0.4))' }}
      />
    </div>
  )
}
