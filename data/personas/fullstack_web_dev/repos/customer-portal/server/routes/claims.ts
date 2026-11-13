import { Router } from "express";
import { z } from "zod";
import { pool } from "../db";
import { requireUser } from "../auth";

const router = Router();

const ClaimInput = z.object({
  policy_number: z.string().min(1),
  amount: z.number().nonnegative(),
  status: z.string().optional(),
});

router.get("/", requireUser, async (req, res) => {
  const { rows } = await pool.query(
    "SELECT * FROM claims WHERE owner_id = $1 ORDER BY created_at DESC LIMIT 100",
    [req.user.id],
  );
  res.json(rows);
});

router.post("/", requireUser, async (req, res) => {
  const parsed = ClaimInput.safeParse(req.body);
  if (!parsed.success) return res.status(422).json({ errors: parsed.error.flatten() });
  const { policy_number, amount, status } = parsed.data;
  const { rows } = await pool.query(
    "INSERT INTO claims (owner_id, policy_number, amount, status) VALUES ($1, $2, $3, $4) RETURNING *",
    [req.user.id, policy_number, amount, status ?? null],
  );
  res.status(201).json(rows[0]);
});

export default router;
