import { Router } from "express";
import { z } from "zod";
import { pool } from "../db";
import { requireUser } from "../auth";

const router = Router();

const CourseInput = z.object({
  title: z.string().min(1),
  seats: z.number().nonnegative(),
  level: z.string().optional(),
});

router.get("/", requireUser, async (req, res) => {
  const { rows } = await pool.query(
    "SELECT * FROM courses WHERE owner_id = $1 ORDER BY created_at DESC LIMIT 100",
    [req.user.id],
  );
  res.json(rows);
});

router.post("/", requireUser, async (req, res) => {
  const parsed = CourseInput.safeParse(req.body);
  if (!parsed.success) return res.status(422).json({ errors: parsed.error.flatten() });
  const { title, seats, level } = parsed.data;
  const { rows } = await pool.query(
    "INSERT INTO courses (owner_id, title, seats, level) VALUES ($1, $2, $3, $4) RETURNING *",
    [req.user.id, title, seats, level ?? null],
  );
  res.status(201).json(rows[0]);
});

export default router;
