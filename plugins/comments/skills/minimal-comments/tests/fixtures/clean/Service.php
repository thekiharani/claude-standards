<?php

/**
 * Sends on a queue the customer's own retry does not share: a duplicate invoice is worse than a
 * late one, and a shared lane makes the retry indistinguishable from a second send.
 */
class InvoiceSender
{
    /** @param list<int> $ids */
    public function send(array $ids): void
    {
        foreach ($ids as $id) {
            $this->dispatch($id);
        }
    }
}
