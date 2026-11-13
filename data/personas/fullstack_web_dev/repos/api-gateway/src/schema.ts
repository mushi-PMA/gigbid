import { gql } from "graphql-tag";

export const typeDefs = gql`
  type Account {
    id: ID!
    owner: String!
    balance: Float!
    currency: String
  }

  type Query {
    accounts(first: Int = 20, after: ID): [Account!]!
    account(id: ID!): Account
  }

  type Mutation {
    createAccount(owner: String!, balance: Float!): Account!
  }
`;

export const resolvers = {
  Query: {
    accounts: (_: unknown, args: { first: number }, ctx: any) => ctx.db.accounts.list(args.first),
    account: (_: unknown, args: { id: string }, ctx: any) => ctx.loaders.accountById.load(args.id),
  },
  Mutation: {
    createAccount: (_: unknown, args: any, ctx: any) => ctx.db.accounts.insert(args),
  },
};
