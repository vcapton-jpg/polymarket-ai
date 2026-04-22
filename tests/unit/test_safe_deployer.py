"""Tests for Safe address computation (no network calls)."""
import pytest
from unittest.mock import MagicMock, patch

from app.trading.safe_deployer import compute_safe_address, SafeDeployer


class TestComputeSafeAddress:
    FACTORY = "0xa6B71E26C5e0845f74c812102Ca7114b6a896AB2"
    SINGLETON = "0xd9Db270c1B5E3Bd161E8c8503c55cEABeE709552"

    def test_returns_checksummed_address(self):
        eoa = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
        addr = compute_safe_address(eoa, singleton=self.SINGLETON, factory=self.FACTORY)
        assert addr.startswith("0x")
        assert len(addr) == 42

    def test_deterministic_for_same_eoa(self):
        eoa = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
        assert (
            compute_safe_address(eoa, self.SINGLETON, self.FACTORY)
            == compute_safe_address(eoa, self.SINGLETON, self.FACTORY)
        )

    def test_different_for_different_eoa(self):
        addr1 = compute_safe_address("0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266", self.SINGLETON, self.FACTORY)
        addr2 = compute_safe_address("0x70997970C51812dc3A010C7d01b50e0d17dc79C8", self.SINGLETON, self.FACTORY)
        assert addr1 != addr2
