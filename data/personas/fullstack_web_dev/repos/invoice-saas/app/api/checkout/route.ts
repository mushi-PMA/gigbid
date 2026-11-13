import { NextResponse } from "next/server";
import Stripe from "stripe";
import { prisma } from "@/lib/prisma";

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!);

export async function POST(request: Request) {
  const { invoiceId } = await request.json();
  const invoice = await prisma.invoice.findUnique({ where: { id: invoiceId } });
  if (!invoice) return NextResponse.json({ error: "not found" }, { status: 404 });

  const session = await stripe.checkout.sessions.create({
    mode: "payment",
    line_items: [{
      quantity: 1,
      price_data: { currency: "usd", unit_amount: Math.round(invoice.total * 100),
                    product_data: { name: invoice.client_name } },
    }],
    metadata: { invoiceId },
    success_url: `${process.env.APP_URL}/thanks?session={CHECKOUT_SESSION_ID}`,
    cancel_url: `${process.env.APP_URL}/`,
  });
  return NextResponse.json({ url: session.url });
}
