import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import AuthScreen from "./AuthScreen";

const auth = vi.hoisted(() => ({
  signIn: { email: vi.fn() },
  signUp: { email: vi.fn() },
  emailOtp: { verifyEmail: vi.fn(), sendVerificationOtp: vi.fn() },
}));

vi.mock("../../services/auth", () => ({ authClient: auth }));

describe("AuthScreen", () => {
  afterEach(() => cleanup());

  beforeEach(() => {
    auth.signIn.email.mockResolvedValue({ data: { user: { id: "user-1" } }, error: null });
    auth.signUp.email.mockResolvedValue({ data: {}, error: null });
    auth.emailOtp.verifyEmail.mockResolvedValue({ data: { status: true }, error: null });
    auth.emailOtp.sendVerificationOtp.mockResolvedValue({ data: { success: true }, error: null });
  });

  it("submits email and password to Neon Auth and restores the session", async () => {
    const onAuthenticated = vi.fn().mockResolvedValue({ id: "user-1" });
    render(<AuthScreen onAuthenticated={onAuthenticated} />);
    fireEvent.change(screen.getByLabelText("Email address"), { target: { value: "person@example.test" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "valid-password" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(auth.signIn.email).toHaveBeenCalledWith({
      email: "person@example.test",
      password: "valid-password",
    }));
    expect(onAuthenticated).toHaveBeenCalledOnce();
  });

  it("shows a Neon Auth error instead of silently reporting success", async () => {
    auth.signIn.email.mockResolvedValue({ data: null, error: { message: "Invalid credentials" } });
    render(<AuthScreen onAuthenticated={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Email address"), { target: { value: "person@example.test" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "wrong-password" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Invalid credentials");
  });

  it("verifies the email code before establishing a sign-in session", async () => {
    const onAuthenticated = vi.fn().mockResolvedValue({ id: "user-1" });
    render(<AuthScreen onAuthenticated={onAuthenticated} />);
    fireEvent.click(screen.getByRole("button", { name: "Create an account" }));
    fireEvent.change(screen.getByLabelText("Your name"), { target: { value: "Avery" } });
    fireEvent.change(screen.getByLabelText("Email address"), { target: { value: "person@example.test" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "valid-password" } });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByRole("heading", { name: "Check your inbox" })).toBeTruthy();
    await waitFor(() => expect(auth.emailOtp.sendVerificationOtp).toHaveBeenCalledWith({
      email: "person@example.test",
      type: "email-verification",
    }));
    fireEvent.change(screen.getByLabelText("Six-digit code"), { target: { value: "123456" } });
    fireEvent.click(screen.getByRole("button", { name: "Verify email" }));

    await waitFor(() => expect(auth.emailOtp.verifyEmail).toHaveBeenCalledWith({
      email: "person@example.test",
      otp: "123456",
    }));
    expect(auth.signIn.email).toHaveBeenCalledWith({
      email: "person@example.test",
      password: "valid-password",
    });
    expect(onAuthenticated).toHaveBeenCalledOnce();
  });

  it("sends a code when Neon Auth rejects sign-in for an unverified email", async () => {
    auth.signIn.email.mockResolvedValue({
      data: null,
      error: { code: "EMAIL_NOT_VERIFIED", message: "Email not verified" },
    });
    render(<AuthScreen onAuthenticated={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Email address"), { target: { value: "person@example.test" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "valid-password" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("heading", { name: "Check your inbox" })).toBeTruthy();
    expect(auth.emailOtp.sendVerificationOtp).toHaveBeenCalledWith({
      email: "person@example.test",
      type: "email-verification",
    });
  });
});
