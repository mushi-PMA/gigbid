library(dplyr)
library(ggplot2)
library(readr)

data <- read_csv("data/arrivals.csv", show_col_types = FALSE) |>
  filter(!is.na(wait_minutes)) |>
  mutate(triage_level = factor(triage_level))

summary_table <- data |>
  group_by(triage_level) |>
  summarise(n = n(), mean = mean(wait_minutes), sd = sd(wait_minutes), median = median(wait_minutes), .groups = "drop")

print(summary_table)
print(kruskal.test(wait_minutes ~ triage_level, data = data))

ggplot(data, aes(x = triage_level, y = wait_minutes)) +
  geom_boxplot(outlier.alpha = 0.3) +
  labs(x = NULL, y = "wait_minutes", title = "Distribution by group") +
  theme_minimal()
ggsave("figures/arrival_boxplot.png", width = 7, height = 4, dpi = 150)
