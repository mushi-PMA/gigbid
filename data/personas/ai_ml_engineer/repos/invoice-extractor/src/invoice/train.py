import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset


class InvoiceDataset(Dataset):
    def __init__(self, features: torch.Tensor, labels: torch.Tensor):
        self.features, self.labels = features, labels

    def __len__(self) -> int:
        return len(self.labels)

    def __getitem__(self, index: int):
        return self.features[index], self.labels[index]


def build_network(input_size: int, classes: int) -> nn.Module:
    return nn.Sequential(
        nn.Linear(input_size, 256), nn.ReLU(), nn.Dropout(0.2),
        nn.Linear(256, 64), nn.ReLU(),
        nn.Linear(64, classes),
    )


def train(dataset: Dataset, input_size: int, classes: int, epochs: int = 12, lr: float = 3e-4) -> nn.Module:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    network = build_network(input_size, classes).to(device)
    optimiser = torch.optim.AdamW(network.parameters(), lr=lr, weight_decay=1e-2)
    loss_fn = nn.CrossEntropyLoss()
    loader = DataLoader(dataset, batch_size=64, shuffle=True)
    for epoch in range(epochs):
        total = 0.0
        for batch_x, batch_y in loader:
            batch_x, batch_y = batch_x.to(device), batch_y.to(device)
            optimiser.zero_grad()
            loss = loss_fn(network(batch_x), batch_y)
            loss.backward()
            optimiser.step()
            total += loss.item() * len(batch_y)
        print(f"epoch {epoch + 1}: loss {total / len(dataset):.4f}")
    return network
