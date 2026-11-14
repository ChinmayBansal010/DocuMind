import { useState } from "react";
import { ArrowLeft, ArrowRight, Check, FileCheck2, LockKeyhole, Mail, ShieldCheck } from "lucide-react";
import { authClient } from "../../services/auth";

export default function AuthScreen({ onAuthenticated }) {
  const [mode, setMode] = useState("sign-in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [verificationCode, setVerificationCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const sendVerificationCode = async () => {
    if (!authClient?.emailOtp?.sendVerificationOtp) {
      throw new Error("Email verification is unavailable. Check the Neon Auth email OTP configuration.");
    }
    const result = await authClient.emailOtp.sendVerificationOtp({
      email,
      type: "email-verification",
    });
    if (result.error) throw new Error(result.error.message || "Unable to send a verification code.");
  };

  const finishSignIn = async () => {
    const sessionUser = await onAuthenticated();
    if (!sessionUser) throw new Error("Neon Auth did not return an active session. Please try signing in again.");
  };

  const submit = async (event) => {
    event.preventDefault();
    setError("");
    setNotice("");
    setBusy(true);
    try {
      if (!authClient) throw new Error("Neon Auth is not configured. Set NEON_AUTH_BASE_URL.");

      if (mode === "verify") {
        const verification = await authClient.emailOtp.verifyEmail({ email, otp: verificationCode.trim() });
        if (verification.error) throw new Error(verification.error.message || "That code could not be verified.");
        const signIn = await authClient.signIn.email({ email, password });
        if (signIn.error) throw new Error(signIn.error.message || "Email verified. Please sign in to continue.");
        await finishSignIn();
        return;
      }

      const result = mode === "sign-in"
        ? await authClient.signIn.email({ email, password })
        : await authClient.signUp.email({ email, password, name });

      if (result.error) {
        const reason = `${result.error.code || ""} ${result.error.message || ""}`;
        if (mode === "sign-in" && /email.?not.?verified|verify.*email|unverified/i.test(reason)) {
          await sendVerificationCode();
          setMode("verify");
          setError("");
          return;
        }
        throw new Error(result.error.message || "Authentication failed.");
      }

      if (mode === "sign-up") {
        setMode("verify");
        setVerificationCode("");
        return;
      }
      await finishSignIn();
    } catch (requestError) {
      setError(requestError.message || "Authentication failed. Try again.");
    } finally {
      setBusy(false);
    }
  };

  const resendCode = async () => {
    setError("");
    setNotice("");
    setBusy(true);
    try {
      await sendVerificationCode();
      setNotice("A new verification code was sent to your email.");
    } catch (requestError) {
      setError(requestError.message || "Unable to send a verification code.");
    } finally {
      setBusy(false);
    }
  };

  const changeMode = (nextMode) => {
    setError("");
    setNotice("");
    setMode(nextMode);
    setVerificationCode("");
  };

  return (
    <main className="auth-page">
      <section className="auth-story">
        <div className="brand"><span className="brand-mark"><FileCheck2 size={20} /></span> DocuMind</div>
        <span className="eyebrow">CONTRACT INTELLIGENCE WORKSPACE</span>
        <h1>Clarity in every agreement.</h1>
        <p>Bring contracts into one secure workspace. Review source-backed findings, obligations, and changes with confidence.</p>
        <div className="auth-benefits">
          <div><span><Check size={14} /></span><div><b>Evidence, not guesswork</b><small>Every finding stays connected to its source.</small></div></div>
          <div><span><Check size={14} /></span><div><b>Your contracts stay private</b><small>Protected workspaces with verified access.</small></div></div>
        </div>
        <div className="trust-note"><LockKeyhole size={15} /> Private project workspaces, protected by Neon Auth</div>
      </section>
      <section className="auth-card">
        <div className="auth-card-icon">{mode === "verify" ? <Mail size={21} /> : <ShieldCheck size={21} />}</div>
        <span className="eyebrow">{mode === "sign-in" ? "WELCOME BACK" : mode === "verify" ? "EMAIL VERIFICATION" : "GET STARTED"}</span>
        <h2>{mode === "sign-in" ? "Sign in to DocuMind" : mode === "verify" ? "Check your inbox" : "Create your account"}</h2>
        <p>{mode === "sign-in"
          ? "Continue to your contract workspace."
          : mode === "verify"
            ? <>Enter the verification code sent to <b className="auth-email">{email}</b>.</>
            : "Your account is managed securely by Neon Auth."}</p>
        <form onSubmit={submit}>
          {mode !== "verify" && mode === "sign-up" && <label>Your name<input autoComplete="name" value={name} onChange={(event) => setName(event.target.value)} required maxLength={200} /></label>}
          {mode !== "verify" && <label>Email address<input type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value.trim())} required /></label>}
          {mode !== "verify" && <label>Password<input type="password" autoComplete={mode === "sign-in" ? "current-password" : "new-password"} value={password} onChange={(event) => setPassword(event.target.value)} minLength={8} required /></label>}
          {mode === "verify" && <label>Six-digit code<input className="verification-input" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" maxLength={6} value={verificationCode} onChange={(event) => setVerificationCode(event.target.value.replace(/\D/g, "").slice(0, 6))} required /></label>}
          {error && <div className="error-box" role="alert">{error}</div>}
          {notice && <div className="error-box" role="status">{notice}</div>}
          <button className="button primary wide" disabled={busy || !authClient || (mode === "verify" && verificationCode.length !== 6)}>
            {busy ? "Please wait…" : mode === "sign-in" ? <>Sign in <ArrowRight size={15} /></> : mode === "verify" ? <>Verify email <ArrowRight size={15} /></> : <>Create account <ArrowRight size={15} /></>}
          </button>
        </form>
        {!authClient && <div className="notice">Authentication is unavailable until the Neon Auth URL is configured.</div>}
        {mode === "verify" ? (
          <div className="auth-verify-actions">
            <button type="button" disabled={busy} onClick={resendCode}>Resend code</button>
            <button type="button" onClick={() => changeMode("sign-in")}><ArrowLeft size={13} /> Back to sign in</button>
          </div>
        ) : (
          <div className="auth-switch">
            {mode === "sign-in" ? "New to DocuMind?" : "Already have an account?"}
            <button type="button" onClick={() => changeMode(mode === "sign-in" ? "sign-up" : "sign-in")}>
              {mode === "sign-in" ? "Create an account" : "Sign in"}
            </button>
          </div>
        )}
        <small className="auth-footnote">By continuing, you agree to use contract analysis as informational support, not legal advice.</small>
      </section>
    </main>
  );
}
