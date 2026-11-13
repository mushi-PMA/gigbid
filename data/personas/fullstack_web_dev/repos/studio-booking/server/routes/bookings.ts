import { Router } from "express";
import { z } from "zod";
import { pool } from "../db";
import { requireUser } from "../auth";

const router = Router();

const BookingInput = z.object({
  class_name: z.string().min(1),
  price: z.number().nonnegative(),
  starts_at: z.string().optional(),
});

router.get("/", requireUser, async (req, res) => {
  const { rows } = await pool.query(
    "SELECT * FROM bookings WHERE owner_id = $1 ORDER BY created_at DESC LIMIT 100",
    [req.user.id],
  );
  res.json(rows);
});

router.post("/", requireUser, async (req, res) => {
  const parsed = BookingInput.safeParse(req.body);
  if (!parsed.success) return res.status(422).json({ errors: parsed.error.flatten() });
  const { class_name, price, starts_at } = parsed.data;
  const { rows } = await pool.query(
    "INSERT INTO bookings (owner_id, class_name, price, starts_at) VALUES ($1, $2, $3, $4) RETURNING *",
    [req.user.id, class_name, price, starts_at ?? null],
  );
  res.status(201).json(rows[0]);
});

export default router;
