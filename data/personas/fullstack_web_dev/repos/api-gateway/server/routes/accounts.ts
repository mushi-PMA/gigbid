import { Router } from "express";
import { z } from "zod";
import { pool } from "../db";
import { requireUser } from "../auth";

const router = Router();

const AccountInput = z.object({
  owner: z.string().min(1),
  balance: z.number().nonnegative(),
  currency: z.string().optional(),
});

router.get("/", requireUser, async (req, res) => {
  const { rows } = await pool.query(
    "SELECT * FROM accounts WHERE owner_id = $1 ORDER BY created_at DESC LIMIT 100",
    [req.user.id],
  );
  res.json(rows);
});

router.post("/", requireUser, async (req, res) => {
  const parsed = AccountInput.safeParse(req.body);
  if (!parsed.success) return res.status(422).json({ errors: parsed.error.flatten() });
  const { owner, balance, currency } = parsed.data;
  const { rows } = await pool.query(
    "INSERT INTO accounts (owner_id, owner, balance, currency) VALUES ($1, $2, $3, $4) RETURNING *",
    [req.user.id, owner, balance, currency ?? null],
  );
  res.status(201).json(rows[0]);
});

export default router;
