/**
 * Razorpay client helper for Eversilver.
 *
 * Loads the Razorpay Checkout JS SDK on demand and opens a UPI-first
 * checkout for the selected tier. The backend creates the subscription
 * and returns a subscription_id, which Razorpay Checkout uses to
 * authorize the recurring UPI mandate or one-time payment.
 */

declare global {
  interface Window {
    Razorpay?: new (options: RazorpayOptions) => RazorpayInstance;
  }
}

export interface RazorpayOptions {
  key: string;
  subscription_id?: string;
  order_id?: string;
  amount?: number;
  currency?: 'INR';
  name: string;
  description?: string;
  image?: string;
  prefill?: { name?: string; email?: string; contact?: string };
  notes?: Record<string, string>;
  theme?: { color?: string };
  /** Restrict checkout to UPI-only when true. */
  method?: { upi?: boolean; card?: boolean; netbanking?: boolean; wallet?: boolean };
  handler: (response: RazorpayResponse) => void;
  modal?: { ondismiss?: () => void };
}

export interface RazorpayResponse {
  razorpay_payment_id: string;
  razorpay_subscription_id?: string;
  razorpay_order_id?: string;
  razorpay_signature: string;
}

interface RazorpayInstance {
  open(): void;
  close(): void;
}

const CHECKOUT_SRC = 'https://checkout.razorpay.com/v1/checkout.js';

let loadingPromise: Promise<void> | null = null;

export function loadRazorpayCheckout(): Promise<void> {
  if (typeof window === 'undefined') return Promise.reject(new Error('Razorpay needs a browser'));
  if (window.Razorpay) return Promise.resolve();
  if (loadingPromise) return loadingPromise;

  loadingPromise = new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = CHECKOUT_SRC;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error('Failed to load Razorpay Checkout SDK'));
    document.head.appendChild(script);
  });
  return loadingPromise;
}

export interface OpenCheckoutArgs {
  /** Razorpay key id (rzp_test_* or rzp_live_*). */
  keyId: string;
  /** Subscription ID returned by your backend (sub_xxxxxxxxxxxx). */
  subscriptionId: string;
  /** Tier label shown in checkout modal. */
  tierName: string;
  /** Public app name shown in checkout. */
  appName?: string;
  /** Optional brand color for the checkout modal (hex). */
  themeColor?: string;
  /** Prefill the modal with the user's profile. */
  prefill?: { name?: string; email?: string; contact?: string };
  /** When true, only show UPI as a payment method. */
  upiOnly?: boolean;
}

export async function openRazorpayCheckout(args: OpenCheckoutArgs): Promise<RazorpayResponse> {
  await loadRazorpayCheckout();
  if (!window.Razorpay) throw new Error('Razorpay not available');

  return new Promise((resolve, reject) => {
    const rzp = new window.Razorpay!({
      key: args.keyId,
      subscription_id: args.subscriptionId,
      name: args.appName ?? 'Eversilver',
      description: `${args.tierName} subscription`,
      currency: 'INR',
      prefill: args.prefill,
      theme: { color: args.themeColor ?? '#5b6478' },
      method: args.upiOnly ? { upi: true, card: false, netbanking: false, wallet: false } : undefined,
      handler: (response) => resolve(response),
      modal: { ondismiss: () => reject(new Error('Checkout dismissed')) },
    });
    rzp.open();
  });
}
