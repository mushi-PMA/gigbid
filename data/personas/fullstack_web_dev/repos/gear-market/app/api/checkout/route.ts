import { NextResponse } from "next/server";
import Stripe from "stripe";
import { prisma } from "@/lib/prisma";

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!);

export async function POST(request: Request) {
  const { listingId } = await request.json();
  const listing = await prisma.listing.findUnique({ where: { id: listingId } });
  if (!listing) return NextResponse.json({ error: "not found" }, { status: 404 });

  const session = await stripe.checkout.sessions.create({
    mode: "payment",
    line_items: [{
      quantity: 1,
      price_data: { currency: "usd", unit_amount: Math.round(listing.price * 100),
                    product_data: { name: listing.title } },
    }],
    metadata: { listingId },
    success_url: `${process.env.APP_URL}/thanks?session={CHECKOUT_SESSION_ID}`,
    cancel_url: `${process.env.APP_URL}/`,
  });
  return NextResponse.json({ url: session.url });
}
